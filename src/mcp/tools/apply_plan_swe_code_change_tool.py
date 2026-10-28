from __future__ import annotations

import difflib
import hashlib
import json
import logging
import re
from pathlib import Path
from typing import Any

from src.llm_client.multi_model_llm_client import MultiModelLLMClient
from src.models.swe_context import SweContext
from src.service.syntax_validator import SyntaxValidationResult, SyntaxValidator
from src.service.tool_prompt_template_service import ToolPromptTemplateService

logger = logging.getLogger(__name__)
SYNTAX_REPAIR_TEMPLATE_NAME = "syntax_repair"

APPLY_OUTCOME_MODIFIED = "modified"
APPLY_OUTCOME_UNCHANGED_MODEL_OUTPUT = "unchanged_model_output"
APPLY_OUTCOME_EMPTY_RESPONSE_FALLBACK = "empty_response_fallback"
APPLY_OUTCOME_SYNTAX_REJECTED_FALLBACK = "syntax_rejected_fallback"
APPLY_OUTCOME_GENERATION_ERROR_FALLBACK = "generation_error_fallback"
APPLY_OUTCOME_GUARDRAIL_BLOCKED = "guardrail_blocked"


class ApplyPlanSweCodeChangeTool:
    """Class-based apply-plan tool for easier mocking and unit testing."""

    def __init__(self, registry) -> None:
        self._registry = registry

    @staticmethod
    def _is_documentation_target(target_path: str) -> bool:
        normalized = target_path.replace("\\", "/").lower()
        if "/docs/" in f"/{normalized}" or normalized.startswith("docs/"):
            return True

        doc_extensions = {
            ".md",
            ".rst",
            ".adoc",
            ".txt",
            ".rtf",
            ".pdf",
            ".doc",
            ".docx",
        }
        return Path(normalized).suffix in doc_extensions

    @staticmethod
    def _sha256_text(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    @staticmethod
    def _classify_apply_outcome(
        *,
        original_code: str,
        generated_code: str,
        empty_generated_guardrail_triggered: bool,
        syntax_rejected: bool,
        generation_error: bool,
        guardrail_blocked: bool,
        raw_response: str = "",
        extracted_blocks: list[dict[str, str]] | None = None,
    ) -> str:
        """Classify why the applied code does or does not differ from the original.

        ``used_fallback_to_original`` only reports textual equality, which merges a
        deliberate no-op from the model with infrastructure fallbacks. This returns
        a single explicit state so reports can tell those cases apart.
        """

        if guardrail_blocked:
            return APPLY_OUTCOME_GUARDRAIL_BLOCKED
        if generation_error:
            return APPLY_OUTCOME_GENERATION_ERROR_FALLBACK
        if empty_generated_guardrail_triggered:
            return APPLY_OUTCOME_EMPTY_RESPONSE_FALLBACK
        if syntax_rejected:
            return APPLY_OUTCOME_SYNTAX_REJECTED_FALLBACK
        if generated_code.strip() != original_code.strip():
            return APPLY_OUTCOME_MODIFIED

        # Output equals the original. A response carrying no usable code means the
        # original was restored by fallback, not that the model chose a no-op.
        if not raw_response.strip() and not (extracted_blocks or []):
            return APPLY_OUTCOME_EMPTY_RESPONSE_FALLBACK
        return APPLY_OUTCOME_UNCHANGED_MODEL_OUTPUT

    @classmethod
    def _build_content_reference(
        cls,
        *,
        target_file: str,
        original_code: str,
        generated_code: str,
        target_language: str | None,
    ) -> dict[str, Any]:
        return {
            "target_file": target_file,
            "target_language": target_language,
            "content_scope": "full_file",
            "original_code_sha256": cls._sha256_text(original_code),
            "generated_code_sha256": cls._sha256_text(generated_code),
            "original_line_count": len(original_code.splitlines()),
            "generated_line_count": len(generated_code.splitlines()),
        }

    @staticmethod
    def _extract_code_blocks(raw_text: str) -> list[dict[str, str]]:
        blocks: list[dict[str, str]] = []
        pattern = re.compile(r"```([a-zA-Z0-9_+-]*)\n(.*?)```", re.DOTALL)
        for match in pattern.finditer(raw_text):
            language = (match.group(1) or "text").strip() or "text"
            content = (match.group(2) or "").strip()
            if content:
                blocks.append({"language": language, "code": content})
        return blocks

    @staticmethod
    def _select_generated_code(
        original_code: str,
        extracted_blocks: list[dict[str, str]],
        raw_text: str,
    ) -> str:
        if extracted_blocks:
            ordered = sorted(
                extracted_blocks, key=lambda b: len(b["code"]), reverse=True
            )
            return ordered[0]["code"]

        stripped = raw_text.strip()
        if stripped and stripped != original_code.strip():
            return stripped
        return original_code

    @staticmethod
    def _truncate_text(value: str | None, max_chars: int) -> str:
        text = (value or "").strip()
        if not text:
            return ""
        if len(text) <= max_chars:
            return text
        return f"{text[:max_chars]}\n\n[...truncated {len(text) - max_chars} chars]"

    @classmethod
    def _compact_swe_context_for_generation(
        cls,
        swe_context: SweContext,
        *,
        max_summary_chars: int,
        max_security_context_chars: int,
    ) -> dict[str, Any]:
        plan = swe_context.plan
        return {
            "nfr_focus": plan.nfr_focus or [],
            "target_language": plan.target_language,
            "high_level_steps": plan.high_level_steps,
            "issue_summary": plan.issue_summary.model_dump()
            if plan.issue_summary
            else None,
            "nfr_discovery": [item.model_dump() for item in plan.nfr_discovery],
            "nfr_discovery_source": plan.nfr_discovery_source,
            "endorsed_entities": plan.related_entities,
            "implementation_plan": [
                step.model_dump() for step in plan.implementation_plan
            ],
            "baseline_context": plan.baseline_context,
            "swe_summary": cls._truncate_text(
                swe_context.swe_summary, max_summary_chars
            ),
            "security_context": cls._truncate_text(
                swe_context.security_context,
                max_security_context_chars,
            )
            or "None",
        }

    @staticmethod
    def _split_code_chunks(
        original_code: str, chunk_lines: int
    ) -> list[dict[str, Any]]:
        lines = original_code.splitlines()
        if not lines:
            return [{"start": 1, "end": 1, "code": ""}]

        chunks: list[dict[str, Any]] = []
        for start_idx in range(0, len(lines), chunk_lines):
            end_idx = min(start_idx + chunk_lines, len(lines))
            chunk_code = "\n".join(lines[start_idx:end_idx])
            chunks.append(
                {
                    "start": start_idx + 1,
                    "end": end_idx,
                    "code": chunk_code,
                }
            )
        return chunks

    @staticmethod
    def _normalize_generated_formatting(original_code: str, generated_code: str) -> str:
        if not generated_code:
            return original_code

        original_lines = original_code.splitlines()
        generated_lines = generated_code.splitlines()
        if not original_lines or not generated_lines:
            return generated_code

        matcher = difflib.SequenceMatcher(
            a=[line.strip() for line in original_lines],
            b=[line.strip() for line in generated_lines],
            autojunk=False,
        )

        normalized_lines: list[str] = []
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                normalized_lines.extend(original_lines[i1:i2])
            else:
                normalized_lines.extend(generated_lines[j1:j2])

        normalized = "\n".join(normalized_lines)
        if generated_code.endswith("\n"):
            normalized += "\n"
        return normalized

    @staticmethod
    def _strip_transport_bom(value: str) -> str:
        return SyntaxValidator.normalize_transport_bom(value)

    @staticmethod
    def _build_single_shot_prompt(
        target_path: str,
        compact_context_json: str,
        original_code: str,
    ) -> str:
        return (
            "You are a senior software engineer applying a planned change to one source file.\n\n"
            "Task: generate the FULL updated file content for the target file.\n"
            "Hard output contract:\n"
            "1) Output exactly one fenced code block.\n"
            "2) Do not output prose, JSON, bullets, or explanations.\n"
            "3) The code block must contain full-file content, not a diff.\n\n"
            "If a structured implementation_plan is supplied, follow its ownership, "
            "requirements and validation. Reuse existing declarations and preserve "
            "files/symbols not assigned for modification.\n"
            f"Target file: {target_path}\n"
            "=== Compact plan/context ===\n"
            f"{compact_context_json}\n\n"
            "=== Original code ===\n"
            f"```\n{original_code}\n```\n"
        )

    @staticmethod
    def _build_chunk_prompt(
        target_path: str,
        compact_context_json: str,
        chunk_index: int,
        chunk_total: int,
        start_line: int,
        end_line: int,
        chunk_code: str,
    ) -> str:
        return (
            "You are editing a chunk of a source file using a global plan.\n\n"
            "Hard output contract:\n"
            "1) Output exactly one fenced code block.\n"
            "2) Return ONLY the updated chunk content for the same line span.\n"
            "3) If no changes are needed in this chunk, return it unchanged.\n"
            "4) No prose or explanations.\n\n"
            "When implementation_plan is supplied, apply only edits assigned to this "
            "file and intersecting this baseline line range. A create action is owned "
            "ONLY by the chunk containing its insertion anchor. Never introduce that "
            "declaration in another chunk. Other baseline declarations are read-only "
            "contracts, not code to duplicate. Return unassigned regions unchanged.\n"
            f"Target file: {target_path}\n"
            f"Chunk: {chunk_index}/{chunk_total} (lines {start_line}-{end_line})\n"
            "=== Compact plan/context ===\n"
            f"{compact_context_json}\n\n"
            "=== Current chunk code ===\n"
            f"```\n{chunk_code}\n```\n"
        )

    @staticmethod
    def _resolve_templates_root(server_context: Any) -> str | None:
        """Resolve the knowledge template root from the server context.

        Returns ``None`` so the template service falls back to its packaged
        default when the context does not expose a usable root.
        """

        configured = getattr(
            getattr(server_context, "config", None), "concern_assets", None
        )
        templates_root = getattr(configured, "templates_root_dir", None)
        repo_root = getattr(server_context, "repo_root", None)

        if not templates_root:
            if not repo_root:
                return None
            return str(Path(repo_root) / "knowledge" / "template")

        path = Path(templates_root)
        if path.is_absolute() or not repo_root:
            return str(path)
        return str(Path(repo_root) / path)

    @staticmethod
    def _build_syntax_repair_prompt(
        target_path: str,
        original_code: str,
        generated_code: str,
        validation: SyntaxValidationResult,
        attempt: int,
        max_attempts: int,
        template_service: ToolPromptTemplateService | None = None,
        review_context: str = "",
    ) -> str:
        diagnostics_json = json.dumps(
            [diagnostic.__dict__ for diagnostic in validation.diagnostics],
            ensure_ascii=False,
            indent=2,
        )
        service = template_service or ToolPromptTemplateService(
            Path(__file__).resolve().parents[3] / "templates", subdirectory="utils"
        )
        return service.render(
            SYNTAX_REPAIR_TEMPLATE_NAME,
            {
                "TARGET_PATH": target_path,
                "ATTEMPT": str(attempt),
                "MAX_ATTEMPTS": str(max_attempts),
                "DIAGNOSTICS_JSON": diagnostics_json,
                "ORIGINAL_CODE": original_code,
                "GENERATED_CODE": generated_code,
                "REVIEW_CONTEXT": review_context,
            },
        )

    def _validate_and_repair_syntax(
        self,
        *,
        llm_client: Any,
        original_code: str,
        generated_code: str,
        target_path: str,
        max_attempts: int,
        max_diagnostics: int,
        chat_kwargs: dict[str, Any],
        template_service: ToolPromptTemplateService | None = None,
        problem_summary: str = "",
    ) -> tuple[str, dict[str, Any]]:
        validator = SyntaxValidator()
        original_validation = validator.validate(
            target_path,
            original_code,
            max_diagnostics=max_diagnostics,
        )
        validation = validator.validate(
            target_path,
            generated_code,
            max_diagnostics=max_diagnostics,
        )
        repair_attempts: list[dict[str, Any]] = []

        def review_candidate(code, facts):
            return validator.review_repair(
                target_path, original_code, code, problem_summary=problem_summary,
                diagnostics=[{"original_parser_facts": original_validation.to_dict(),
                              "candidate_parser_facts": facts.to_dict()}],
            )

        review = review_candidate(generated_code, validation)
        initial_review = review.model_dump()

        for attempt in range(1, max_attempts + 1):
            if review.approved:
                break
            prompt = self._build_syntax_repair_prompt(
                target_path=target_path,
                original_code=original_code,
                generated_code=generated_code,
                validation=validation,
                attempt=attempt,
                max_attempts=max_attempts,
                template_service=template_service,
                review_context=json.dumps({"requirements": problem_summary, "review": review.model_dump()}),
            )
            raw_response = llm_client.chat(prompt, **chat_kwargs)
            repaired_code = self._select_generated_code(
                generated_code, self._extract_code_blocks(raw_response), raw_response,
            )
            generated_code = self._normalize_generated_formatting(
                original_code=generated_code, generated_code=repaired_code,
            )
            validation = validator.validate(
                target_path, generated_code, max_diagnostics=max_diagnostics,
            )
            review = review_candidate(generated_code, validation)
            repair_attempts.append({
                "attempt": attempt, "validation": validation.to_dict(),
                "semantic_review": review.model_dump(),
            })

        rejected = not review.approved
        if rejected:
            generated_code = original_code

        return generated_code, {
            "available": validation.available,
            "original": original_validation.to_dict(),
            "final": validation.to_dict(),
            "repair_attempts": repair_attempts,
            "initial_semantic_review": initial_review,
            "final_semantic_review": review.model_dump(),
            "rejected_invalid_generation": rejected,
        }

    def execute(
        self,
        swe_context: SweContext,
        original_code: str,
        target_file: str | None = None,
        temperature: float | None = None,
        seed: int | None = None,
    ) -> dict[str, Any]:
        """Generate candidate modified code using plan + context + original code."""

        llm_cls = self._registry._llm_client_cls or MultiModelLLMClient

        server_context = self._registry._create_swe_server_context()
        config = server_context.config.execution
        template_service = ToolPromptTemplateService(
            self._resolve_templates_root(server_context)
        )

        target_path = target_file or "target_file"
        target_language = swe_context.plan.target_language
        implementation = swe_context.plan.implementation_plan
        assignments = [
            step
            for step in implementation
            if step.target_file == target_path and step.action != "reuse"
        ]
        if implementation and not self._is_documentation_target(target_path):
            baseline = swe_context.plan.baseline_context.get(target_path)
            if not baseline or baseline.get("sha256") != self._sha256_text(
                original_code
            ):
                raise ValueError(
                    f"Code does not match the grounded plan baseline: {target_path}"
                )
            if not assignments:
                logger.info(
                    "Preserving %s: no edits assigned by the validated plan",
                    target_path,
                )
                return {
                    "target_file": target_path,
                    "generated_code": original_code,
                    "raw_response": "",
                    "extracted_code_blocks": [],
                    "used_fallback_to_original": False,
                    "apply_outcome": "unchanged_plan_scope",
                    "error": None,
                    "prompt": "[no edits assigned by grounded plan]",
                    "compact_context": {},
                    "chunked": False,
                    "chunk_count": 0,
                    "chunk_errors": [],
                    "content_reference": self._build_content_reference(
                        target_file=target_path,
                        original_code=original_code,
                        generated_code=original_code,
                        target_language=target_language,
                    ),
                }

        if self._is_documentation_target(target_path):
            guardrail_error = (
                "Guardrail blocked apply_plan_swe_code_change for documentation "
                f"target: {target_path}"
            )
            return {
                "target_file": target_path,
                "generated_code": original_code,
                "raw_response": "",
                "extracted_code_blocks": [],
                "used_fallback_to_original": True,
                "apply_outcome": APPLY_OUTCOME_GUARDRAIL_BLOCKED,
                "error": guardrail_error,
                "guardrail_blocked": True,
                "prompt": "[guardrail-blocked: documentation target]",
                "compact_context": {
                    "nfr_focus": swe_context.plan.nfr_focus or [],
                    "target_language": target_language,
                    "high_level_steps": swe_context.plan.high_level_steps,
                    "swe_summary": "[guardrail-blocked]",
                    "security_context": "[guardrail-blocked]",
                },
                "chunked": False,
                "content_reference": self._build_content_reference(
                    target_file=target_path,
                    original_code=original_code,
                    generated_code=original_code,
                    target_language=target_language,
                ),
            }

        compact_context = self._compact_swe_context_for_generation(
            swe_context,
            max_summary_chars=config.max_summary_chars,
            max_security_context_chars=config.max_security_context_chars,
        )
        compact_context_json = json.dumps(compact_context, ensure_ascii=False, indent=2)
        llm_client = llm_cls()
        chunked = len(original_code) > config.max_single_shot_code_chars
        max_concurrency = int(getattr(config, "max_generation_concurrency", 1))
        logger.info(
            "Generating %s (chars=%s, chunked=%s, concurrency_limit=%s)",
            target_path,
            len(original_code),
            chunked,
            max_concurrency,
        )

        chat_kwargs: dict[str, Any] = {}
        if temperature is not None:
            chat_kwargs["temperature"] = temperature
        if seed is not None:
            chat_kwargs["seed"] = seed

        if not chunked:
            prompt = self._build_single_shot_prompt(
                target_path=target_path,
                compact_context_json=compact_context_json,
                original_code=original_code,
            )
            try:
                raw_response = llm_client.chat(prompt, **chat_kwargs)
            except Exception as exc:  # pragma: no cover
                self._registry._logger.warning(
                    "apply_plan_swe_code_change failed for %s: %s",
                    target_path,
                    exc,
                    exc_info=True,
                )
                return {
                    "target_file": target_path,
                    "generated_code": original_code,
                    "raw_response": "",
                    "extracted_code_blocks": [],
                    "used_fallback_to_original": True,
                    "apply_outcome": APPLY_OUTCOME_GENERATION_ERROR_FALLBACK,
                    "error": f"{type(exc).__name__}: {exc}",
                    "prompt": prompt,
                    "compact_context": compact_context,
                    "chunked": False,
                    "content_reference": self._build_content_reference(
                        target_file=target_path,
                        original_code=original_code,
                        generated_code=original_code,
                        target_language=target_language,
                    ),
                }

            extracted_blocks = self._extract_code_blocks(raw_response)
            generated_code = self._select_generated_code(
                original_code, extracted_blocks, raw_response
            )
            chunk_errors: list[dict[str, Any]] = []
        else:
            chunks = self._split_code_chunks(
                original_code, chunk_lines=config.chunk_lines
            )
            updated_chunks: list[str] = [str(chunk["code"]) for chunk in chunks]
            raw_responses: list[str] = []
            chunk_errors = []

            selected_chunks = [
                (idx, chunk)
                for idx, chunk in enumerate(chunks, start=1)
                if not implementation
                or any(
                    step.start_line <= int(chunk["end"])
                    and step.end_line >= int(chunk["start"])
                    for step in assignments
                )
            ]
            chunk_prompts = [
                self._build_chunk_prompt(
                    target_path=target_path,
                    compact_context_json=compact_context_json,
                    chunk_index=idx,
                    chunk_total=len(chunks),
                    start_line=int(chunk["start"]),
                    end_line=int(chunk["end"]),
                    chunk_code=str(chunk["code"]),
                )
                for idx, chunk in selected_chunks
            ]
            batch_chat = getattr(llm_client, "chat_batch", None)
            responses = (
                batch_chat(
                    chunk_prompts, max_concurrency=max_concurrency, **chat_kwargs
                )
                if max_concurrency > 1 and callable(batch_chat)
                else None
            )

            for response_index, ((idx, chunk), chunk_prompt) in enumerate(
                zip(selected_chunks, chunk_prompts, strict=True)
            ):
                try:
                    chunk_raw = (
                        responses[response_index]
                        if responses is not None
                        else llm_client.chat(chunk_prompt, **chat_kwargs)
                    )
                    if isinstance(chunk_raw, Exception):
                        raise chunk_raw
                    chunk_blocks = self._extract_code_blocks(chunk_raw)
                    updated_chunk = self._select_generated_code(
                        str(chunk["code"]),
                        chunk_blocks,
                        chunk_raw,
                    )
                    updated_chunks[idx - 1] = updated_chunk
                    raw_responses.append(
                        f"### Chunk {idx}/{len(chunks)} (lines {chunk['start']}-{chunk['end']})\\n{chunk_raw}"
                    )
                    logger.info(
                        "Generated %s chunk %s/%s (lines %s-%s)",
                        target_path,
                        idx,
                        len(chunks),
                        chunk["start"],
                        chunk["end"],
                    )
                except Exception as exc:  # pragma: no cover
                    self._registry._logger.warning(
                        "Chunk generation failed for %s (chunk %s/%s, lines %s-%s): %s",
                        target_path,
                        idx,
                        len(chunks),
                        chunk["start"],
                        chunk["end"],
                        exc,
                        exc_info=True,
                    )
                    chunk_errors.append(
                        {
                            "chunk_index": idx,
                            "line_start": chunk["start"],
                            "line_end": chunk["end"],
                            "error": f"{type(exc).__name__}: {exc}",
                        }
                    )

            generated_code = "\n".join(updated_chunks)
            raw_response = "\n\n".join(raw_responses)
            extracted_blocks = self._extract_code_blocks(raw_response)
            prompt = "[chunked-mode: per-chunk prompts generated dynamically]"

        generated_code = self._normalize_generated_formatting(
            original_code=original_code,
            generated_code=generated_code,
        )
        generated_code = self._strip_transport_bom(generated_code)

        empty_generated_guardrail_triggered = False
        if not generated_code.strip():
            generated_code = original_code
            empty_generated_guardrail_triggered = True

        max_repair_attempts = int(getattr(config, "max_syntax_repair_attempts", 2))
        max_syntax_diagnostics = int(getattr(config, "max_syntax_diagnostics", 20))
        generated_code, syntax_validation = self._validate_and_repair_syntax(
            llm_client=llm_client,
            original_code=original_code,
            generated_code=generated_code,
            target_path=target_path,
            max_attempts=max_repair_attempts,
            max_diagnostics=max_syntax_diagnostics,
            chat_kwargs=chat_kwargs,
            problem_summary=swe_context.plan.model_dump_json() + "\n" + swe_context.swe_summary,
        )
        syntax_rejected = bool(
            syntax_validation.get("rejected_invalid_generation", False)
        )

        unchanged = generated_code.strip() == original_code.strip()
        chunk_generation_failed = bool(chunk_errors) and unchanged

        apply_outcome = self._classify_apply_outcome(
            original_code=original_code,
            generated_code=generated_code,
            empty_generated_guardrail_triggered=empty_generated_guardrail_triggered,
            syntax_rejected=syntax_rejected,
            generation_error=chunk_generation_failed,
            guardrail_blocked=False,
            raw_response=raw_response,
            extracted_blocks=extracted_blocks,
        )

        return {
            "target_file": target_path,
            "generated_code": generated_code,
            "raw_response": raw_response,
            "extracted_code_blocks": extracted_blocks,
            "used_fallback_to_original": unchanged,
            "apply_outcome": apply_outcome,
            "prompt": prompt,
            "compact_context": compact_context,
            "chunked": chunked,
            "chunk_line_size": config.chunk_lines if chunked else None,
            "chunk_count": len(
                self._split_code_chunks(original_code, chunk_lines=config.chunk_lines)
            )
            if chunked
            else 1,
            "chunk_errors": chunk_errors if chunked else [],
            "formatting_normalized": True,
            "empty_generated_guardrail_triggered": empty_generated_guardrail_triggered,
            "syntax_validation": syntax_validation,
            "execution_config": {
                "max_summary_chars": config.max_summary_chars,
                "max_security_context_chars": config.max_security_context_chars,
                "max_single_shot_code_chars": config.max_single_shot_code_chars,
                "chunk_lines": config.chunk_lines,
                "max_syntax_repair_attempts": max_repair_attempts,
                "max_syntax_diagnostics": max_syntax_diagnostics,
            },
            "content_reference": self._build_content_reference(
                target_file=target_path,
                original_code=original_code,
                generated_code=generated_code,
                target_language=target_language,
            ),
            "error": (
                "Guardrail fallback: generated code was empty after normalization."
                if empty_generated_guardrail_triggered
                else (
                    "LLM review rejected the generated code "
                    "after bounded repair attempts."
                    if syntax_rejected
                    else None
                )
            ),
        }
