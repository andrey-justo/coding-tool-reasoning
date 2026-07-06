from __future__ import annotations

import difflib
import json
import re
from typing import Any

from src.llm_client.multi_model_llm_client import MultiModelLLMClient
from src.models.swe_context import SweContext


class ApplyPlanSweCodeChangeTool:
    """Class-based apply-plan tool for easier mocking and unit testing."""

    def __init__(self, registry) -> None:
        self._registry = registry

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
            f"Target file: {target_path}\n"
            f"Chunk: {chunk_index}/{chunk_total} (lines {start_line}-{end_line})\n"
            "=== Compact plan/context ===\n"
            f"{compact_context_json}\n\n"
            "=== Current chunk code ===\n"
            f"```\n{chunk_code}\n```\n"
        )

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
        llm_client = llm_cls()

        config = self._registry._create_swe_server_context().config.execution

        target_path = target_file or "target_file"
        compact_context = self._compact_swe_context_for_generation(
            swe_context,
            max_summary_chars=config.max_summary_chars,
            max_security_context_chars=config.max_security_context_chars,
        )
        compact_context_json = json.dumps(compact_context, ensure_ascii=False, indent=2)
        chunked = len(original_code) > config.max_single_shot_code_chars

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
                    "apply_plan_swe_code_change failed: %s", exc
                )
                return {
                    "target_file": target_path,
                    "generated_code": original_code,
                    "raw_response": "",
                    "extracted_code_blocks": [],
                    "used_fallback_to_original": True,
                    "error": f"{type(exc).__name__}: {exc}",
                    "prompt": prompt,
                    "compact_context": compact_context,
                    "chunked": False,
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
            updated_chunks: list[str] = []
            raw_responses: list[str] = []
            chunk_errors = []

            for idx, chunk in enumerate(chunks, start=1):
                chunk_prompt = self._build_chunk_prompt(
                    target_path=target_path,
                    compact_context_json=compact_context_json,
                    chunk_index=idx,
                    chunk_total=len(chunks),
                    start_line=int(chunk["start"]),
                    end_line=int(chunk["end"]),
                    chunk_code=str(chunk["code"]),
                )

                try:
                    chunk_raw = llm_client.chat(chunk_prompt, **chat_kwargs)
                    chunk_blocks = self._extract_code_blocks(chunk_raw)
                    updated_chunk = self._select_generated_code(
                        str(chunk["code"]),
                        chunk_blocks,
                        chunk_raw,
                    )
                    updated_chunks.append(updated_chunk)
                    raw_responses.append(
                        f"### Chunk {idx}/{len(chunks)} (lines {chunk['start']}-{chunk['end']})\\n{chunk_raw}"
                    )
                except Exception as exc:  # pragma: no cover
                    chunk_errors.append(
                        {
                            "chunk_index": idx,
                            "line_start": chunk["start"],
                            "line_end": chunk["end"],
                            "error": f"{type(exc).__name__}: {exc}",
                        }
                    )
                    updated_chunks.append(str(chunk["code"]))

            generated_code = "\n".join(updated_chunks)
            raw_response = "\n\n".join(raw_responses)
            extracted_blocks = self._extract_code_blocks(raw_response)
            prompt = "[chunked-mode: per-chunk prompts generated dynamically]"

        generated_code = self._normalize_generated_formatting(
            original_code=original_code,
            generated_code=generated_code,
        )

        return {
            "target_file": target_path,
            "generated_code": generated_code,
            "raw_response": raw_response,
            "extracted_code_blocks": extracted_blocks,
            "used_fallback_to_original": generated_code.strip()
            == original_code.strip(),
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
            "execution_config": {
                "max_summary_chars": config.max_summary_chars,
                "max_security_context_chars": config.max_security_context_chars,
                "max_single_shot_code_chars": config.max_single_shot_code_chars,
                "chunk_lines": config.chunk_lines,
            },
        }
