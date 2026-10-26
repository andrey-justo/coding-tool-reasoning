from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from src.llm_client.multi_model_llm_client import MultiModelLLMClient
from src.mcp.tools.apply_plan_swe_code_change_tool import ApplyPlanSweCodeChangeTool
from src.service.ast_context_service import AstContextService
from src.service.build_diagnostics import (
    BuildDiagnosticContext,
    BuildDiagnosticParserResolver,
    match_diagnostic_file,
)
from src.service.language_detection import infer_language_from_file_paths
from src.service.semantic_context_service import SemanticContextService
from src.service.symbol_context_service import RepositorySymbolContextService
from src.service.syntax_validator import SyntaxValidator
from src.service.tool_prompt_template_service import ToolPromptTemplateService

BUILD_REPAIR_TEMPLATE_NAME = "build_repair"
BUILD_REPAIR_CHUNK_TEMPLATE_NAME = "build_repair_chunk_v1"


class RepairBuildFailureTool:
    """Repair compilation failures using build diagnostics and AST context.

    Syntax validation only proves a file parses; it cannot detect semantic
    compiler errors such as an argument type mismatch. This tool closes that gap
    by feeding parsed build diagnostics, the enclosing AST declarations and the
    original problem summary back to the model, one failing file at a time.
    """

    def __init__(self, registry) -> None:
        self._registry = registry

    def _execution_config(self) -> Any:
        try:
            return self._registry._create_swe_server_context().config.execution
        except Exception:  # pragma: no cover - defensive for minimal registries
            return None

    def _verification_project_type(self) -> str:
        try:
            verification = (
                self._registry._create_swe_server_context().config.verification
            )
            return str(getattr(verification, "project_type", "auto") or "auto")
        except Exception:  # pragma: no cover - defensive for minimal registries
            return "auto"

    def _template_service(self) -> ToolPromptTemplateService:
        try:
            server_context = self._registry._create_swe_server_context()
            return ToolPromptTemplateService(
                ApplyPlanSweCodeChangeTool._resolve_templates_root(server_context)
            )
        except Exception:  # pragma: no cover - defensive for minimal registries
            return ToolPromptTemplateService()

    @staticmethod
    def _tail(value: str, max_chars: int) -> str:
        if max_chars <= 0 or len(value) <= max_chars:
            return value
        return value[-max_chars:]

    @staticmethod
    def _infer_source_generator_target(
        diagnostic: Any,
        known_files: list[str],
    ) -> str | None:
        """Map source-generator diagnostics back to an editable generator file."""

        generator_files = [
            path
            for path in known_files
            if Path(path.replace("\\", "/")).name.lower().endswith("generator.cs")
        ]
        if not generator_files:
            return None

        diagnostic_file = str(getattr(diagnostic, "file", "") or "")
        normalized_file = diagnostic_file.replace("\\", "/").lower()

        if normalized_file.endswith(".g.cs") or "/obj/" in normalized_file:
            matching_generators = [
                path
                for path in generator_files
                if Path(path.replace("\\", "/")).stem.lower() in normalized_file
            ]
            if len(matching_generators) == 1:
                return matching_generators[0]

        code = str(getattr(diagnostic, "code", "") or "").upper()
        compiler_source = normalized_file.strip().rstrip(":") in {"csc", "fsc"}
        standard_compiler_diagnostic = code.startswith(("CS", "FS", "BC"))
        if (
            compiler_source
            and code
            and not standard_compiler_diagnostic
            and len(generator_files) == 1
        ):
            return generator_files[0]

        return None

    @classmethod
    def _route_diagnostics(
        cls,
        diagnostics: list[Any],
        known_files: list[str],
    ) -> tuple[
        dict[str, list[dict[str, Any]]],
        list[dict[str, Any]],
        list[dict[str, Any]],
        list[dict[str, str]],
    ]:
        directly_mapped: dict[str, list[dict[str, Any]]] = {}
        generator_mapped: dict[str, list[dict[str, Any]]] = {}
        unmatched: list[dict[str, Any]] = []
        inferred_mappings: list[dict[str, str]] = []

        for diagnostic in diagnostics:
            target_file = match_diagnostic_file(diagnostic.file, known_files)
            if target_file is not None:
                directly_mapped.setdefault(target_file, []).append(
                    diagnostic.to_dict()
                )
                continue

            target_file = cls._infer_source_generator_target(
                diagnostic,
                known_files,
            )
            if target_file is None:
                unmatched.append(diagnostic.to_dict())
                continue

            generator_mapped.setdefault(target_file, []).append(diagnostic.to_dict())
            inferred_mappings.append(
                {
                    "diagnostic_file": str(diagnostic.file or ""),
                    "diagnostic_code": str(diagnostic.code or ""),
                    "target_file": target_file,
                }
            )

        if not generator_mapped:
            return directly_mapped, unmatched, [], inferred_mappings

        # Generated-code diagnostics identify an upstream cause. Repair that
        # source generator first and defer consumer errors until the next build.
        deferred: list[dict[str, Any]] = []
        for target_file, items in directly_mapped.items():
            if target_file in generator_mapped:
                generator_mapped[target_file].extend(items)
            else:
                deferred.extend(items)

        return generator_mapped, unmatched, deferred, inferred_mappings

    @staticmethod
    def _build_repair_prompt(
        *,
        problem_summary: str,
        target_path: str,
        current_code: str,
        diagnostics: list[dict[str, Any]],
        repair_history: list[dict[str, Any]],
        ast_context: list[dict[str, Any]],
        semantic_context: list[dict[str, Any]],
        related_symbols: list[dict[str, Any]],
        build_command: list[str] | None,
        build_output_tail: str,
        attempt: int,
        max_attempts: int,
        template_service: ToolPromptTemplateService,
    ) -> str:
        return template_service.render(
            BUILD_REPAIR_TEMPLATE_NAME,
            {
                "PROBLEM_SUMMARY": problem_summary.strip()
                or "[no problem summary provided]",
                "TARGET_PATH": target_path,
                "ATTEMPT": str(attempt),
                "MAX_ATTEMPTS": str(max_attempts),
                "BUILD_COMMAND": " ".join(build_command) if build_command else "n/a",
                "DIAGNOSTICS_JSON": json.dumps(
                    diagnostics, ensure_ascii=False, indent=2
                ),
                "REPAIR_HISTORY_JSON": json.dumps(
                    repair_history, ensure_ascii=False, indent=2
                ),
                "AST_CONTEXT_JSON": json.dumps(
                    ast_context, ensure_ascii=False, indent=2
                ),
                "SEMANTIC_CONTEXT_JSON": json.dumps(
                    semantic_context, ensure_ascii=False, indent=2
                ),
                "RELATED_SYMBOLS_JSON": json.dumps(
                    related_symbols, ensure_ascii=False, indent=2
                ),
                "BUILD_OUTPUT_TAIL": build_output_tail,
                "CURRENT_CODE": current_code,
            },
        )

    @staticmethod
    def _relevance_tokens(value: str) -> set[str]:
        ignored = {
            "and",
            "are",
            "build",
            "class",
            "code",
            "compile",
            "compiler",
            "error",
            "file",
            "from",
            "must",
            "public",
            "return",
            "source",
            "that",
            "the",
            "this",
            "using",
            "with",
        }
        return {
            token.lower()
            for token in re.findall(r"[A-Za-z_][A-Za-z0-9_]{2,}", value)
            if token.lower() not in ignored
        }

    @classmethod
    def _escalation_targets(
        cls,
        *,
        diagnostics_by_file: dict[str, list[dict[str, Any]]],
        extra_diagnostics: list[dict[str, Any]],
        code_by_file: dict[str, str],
        max_targets: int,
    ) -> dict[str, list[dict[str, Any]]]:
        """Route stalled diagnostics to the files their message actually names.

        A diagnostic emitted by a tool rather than by a file position is first
        attributed to a single plausible owner. When repairing that owner yields
        no change, the owner is not where the fix belongs, and the message text
        is the only remaining signal, so the files it names are tried next
        instead of abandoning the repair budget.
        """

        if max_targets <= 0:
            return {}

        pending = [
            diagnostic
            for diagnostics in diagnostics_by_file.values()
            for diagnostic in diagnostics
        ]
        pending.extend(extra_diagnostics)
        already_targeted = set(diagnostics_by_file)

        escalated: dict[str, list[dict[str, Any]]] = {}
        for diagnostic in pending:
            tokens = cls._relevance_tokens(str(diagnostic.get("message") or ""))
            if not tokens:
                continue

            ranked: list[tuple[int, str]] = []
            for path, code in code_by_file.items():
                if path in already_targeted:
                    continue
                # A name in the path is a stronger ownership signal than the
                # same name appearing somewhere in the body of a file.
                score = 2 * len(tokens & cls._relevance_tokens(path)) + len(
                    tokens & cls._relevance_tokens(code)
                )
                if score:
                    ranked.append((score, path))

            ranked.sort(key=lambda item: (-item[0], item[1]))
            for _, path in ranked[:max_targets]:
                bucket = escalated.setdefault(path, [])
                if diagnostic not in bucket:
                    bucket.append(diagnostic)

        return escalated

    @classmethod
    def _select_repair_chunks(
        cls,
        chunks: list[dict[str, Any]],
        diagnostics: list[dict[str, Any]],
        problem_summary: str,
        *,
        max_chunks: int,
    ) -> list[dict[str, Any]]:
        diagnostic_lines = [
            int(diagnostic["line"])
            for diagnostic in diagnostics
            if diagnostic.get("line")
        ]
        relevance_text = " ".join(
            [
                problem_summary,
                *[
                    " ".join(
                        str(diagnostic.get(key) or "")
                        for key in ("code", "message", "file")
                    )
                    for diagnostic in diagnostics
                ],
            ]
        )
        relevance_tokens = cls._relevance_tokens(relevance_text)

        ranked: list[dict[str, Any]] = []
        for index, chunk in enumerate(chunks):
            positioned_lines = [
                line
                for line in diagnostic_lines
                if int(chunk["start"]) <= line <= int(chunk["end"])
            ]
            chunk_tokens = cls._relevance_tokens(str(chunk["code"]))
            ranked.append(
                {
                    **chunk,
                    "index": index,
                    "positioned_diagnostic_lines": positioned_lines,
                    "lexical_score": len(relevance_tokens & chunk_tokens),
                    "selection_reason": (
                        "diagnostic_line" if positioned_lines else "lexical_relevance"
                    ),
                }
            )

        positioned = sorted(
            (chunk for chunk in ranked if chunk["positioned_diagnostic_lines"]),
            key=lambda chunk: (
                min(chunk["positioned_diagnostic_lines"]),
                chunk["index"],
            ),
        )
        selected_indexes = {chunk["index"] for chunk in positioned[:max_chunks]}
        selected = positioned[:max_chunks]
        if len(selected) < max_chunks:
            lexical = sorted(
                (
                    chunk
                    for chunk in ranked
                    if chunk["index"] not in selected_indexes
                ),
                key=lambda chunk: (-chunk["lexical_score"], chunk["index"]),
            )
            selected.extend(lexical[: max_chunks - len(selected)])
        return selected

    @staticmethod
    def _build_chunk_repair_prompt(
        *,
        problem_summary: str,
        target_path: str,
        chunk: dict[str, Any],
        total_chunks: int,
        diagnostics: list[dict[str, Any]],
        repair_history: list[dict[str, Any]],
        ast_context: list[dict[str, Any]],
        semantic_context: list[dict[str, Any]],
        related_symbols: list[dict[str, Any]],
        build_command: list[str] | None,
        build_output_tail: str,
        attempt: int,
        max_attempts: int,
        template_service: ToolPromptTemplateService,
    ) -> str:
        return template_service.render(
            BUILD_REPAIR_CHUNK_TEMPLATE_NAME,
            {
                "PROBLEM_SUMMARY": problem_summary.strip()
                or "[no problem summary provided]",
                "TARGET_PATH": target_path,
                "ATTEMPT": str(attempt),
                "MAX_ATTEMPTS": str(max_attempts),
                "BUILD_COMMAND": " ".join(build_command) if build_command else "n/a",
                "CHUNK_NUMBER": str(int(chunk["index"]) + 1),
                "TOTAL_CHUNKS": str(total_chunks),
                "CHUNK_START_LINE": str(chunk["start"]),
                "CHUNK_END_LINE": str(chunk["end"]),
                "DIAGNOSTICS_JSON": json.dumps(
                    diagnostics, ensure_ascii=False, indent=2
                ),
                "REPAIR_HISTORY_JSON": json.dumps(
                    repair_history, ensure_ascii=False, indent=2
                ),
                "AST_CONTEXT_JSON": json.dumps(
                    ast_context, ensure_ascii=False, indent=2
                ),
                "SEMANTIC_CONTEXT_JSON": json.dumps(
                    semantic_context, ensure_ascii=False, indent=2
                ),
                "RELATED_SYMBOLS_JSON": json.dumps(
                    related_symbols, ensure_ascii=False, indent=2
                ),
                "BUILD_OUTPUT_TAIL": build_output_tail,
                "CURRENT_CHUNK": str(chunk["code"]),
            },
        )

    @staticmethod
    def _is_destructively_truncated(original: str, repaired: str) -> bool:
        original_lines = original.splitlines()
        repaired_lines = repaired.splitlines()
        if len(original_lines) < 8 or len(original) < 200:
            return False
        return (
            len(repaired_lines) * 2 < len(original_lines)
            and len(repaired) * 2 < len(original)
        )

    @staticmethod
    def _merge_repaired_chunks(
        chunks: list[dict[str, Any]],
        repaired_by_index: dict[int, str],
        *,
        final_newline: bool,
    ) -> str:
        merged = "\n".join(
            repaired_by_index.get(index, str(chunk["code"]))
            for index, chunk in enumerate(chunks)
        )
        if final_newline:
            return merged + "\n"
        return merged

    def execute(
        self,
        problem_summary: str,
        build_output: str,
        generated_code_by_file: dict[str, str],
        build_command: list[str] | None = None,
        attempt: int = 1,
        max_attempts: int = 10,
        temperature: float | None = None,
        seed: int | None = None,
        repo_path: str | None = None,
        repair_history: list[dict[str, Any]] | None = None,
        escalate_routing: bool = False,
    ) -> dict[str, Any]:
        """Produce repaired file contents for files reported by the build."""

        config = self._execution_config()
        max_diagnostics = int(getattr(config, "max_build_diagnostics", 20) or 20)
        max_output_chars = int(getattr(config, "max_build_output_chars", 6000) or 6000)
        max_ast_locations = int(getattr(config, "max_build_ast_locations", 5) or 5)
        max_syntax_diagnostics = int(
            getattr(config, "max_syntax_diagnostics", 20) or 20
        )
        max_related_symbols = int(getattr(config, "max_related_symbols", 8) or 8)
        max_related_symbol_files = int(
            getattr(config, "max_related_symbol_files", 5) or 5
        )
        max_related_declarations = int(
            getattr(config, "max_related_declarations", 12) or 12
        )
        max_single_shot_code_chars = int(
            getattr(config, "max_single_shot_code_chars", 12000) or 12000
        )
        chunk_lines = int(getattr(config, "chunk_lines", 160) or 160)
        max_build_repair_chunks = int(
            getattr(config, "max_build_repair_chunks", 4) or 4
        )
        max_semantic_diagnostics = int(
            getattr(config, "max_semantic_diagnostics", 6) or 6
        )
        max_escalated_targets = int(
            getattr(config, "max_escalated_repair_targets", 2) or 2
        )
        recent_repair_history = list(repair_history or [])[-5:]

        repaired_code_by_file = dict(generated_code_by_file)
        diagnostics_result = BuildDiagnosticParserResolver().parse(
            build_output or "",
            BuildDiagnosticContext(
                language=infer_language_from_file_paths(list(generated_code_by_file)),
                project_type=self._verification_project_type(),
                changed_files=tuple(generated_code_by_file),
            ),
            max_diagnostics=max_diagnostics,
        )

        (
            diagnostics_by_file,
            unmatched,
            deferred,
            inferred_mappings,
        ) = self._route_diagnostics(
            diagnostics_result.diagnostics,
            list(generated_code_by_file),
        )

        escalated_targets: list[str] = []
        if escalate_routing:
            escalated = self._escalation_targets(
                diagnostics_by_file=diagnostics_by_file,
                extra_diagnostics=deferred + unmatched,
                code_by_file=generated_code_by_file,
                max_targets=max_escalated_targets,
            )
            for path, extra in escalated.items():
                diagnostics_by_file.setdefault(path, []).extend(extra)
            escalated_targets = sorted(escalated)

        result: dict[str, Any] = {
            "attempt": int(attempt),
            "max_attempts": int(max_attempts),
            "diagnostics_parser": diagnostics_result.parser,
            "diagnostics_by_file": diagnostics_by_file,
            "unmatched_diagnostics": unmatched,
            "deferred_diagnostics": deferred,
            "inferred_diagnostic_mappings": inferred_mappings,
            "escalated_targets": escalated_targets,
            "generated_code_by_file": repaired_code_by_file,
            "file_results": [],
            "repaired_files": [],
            "changed": False,
            "repair_history_size": len(recent_repair_history),
        }

        if not diagnostics_by_file:
            result["error"] = (
                "No build diagnostics could be mapped to the generated files; "
                "automated build repair cannot target a file."
            )
            return result

        llm_cls = self._registry._llm_client_cls or MultiModelLLMClient
        llm_client = llm_cls()
        template_service = self._template_service()
        validator = SyntaxValidator()
        ast_service = AstContextService()
        symbol_context_service = RepositorySymbolContextService()
        semantic_service = SemanticContextService()
        build_output_tail = self._tail(build_output or "", max_output_chars)

        chat_kwargs: dict[str, Any] = {}
        if temperature is not None:
            chat_kwargs["temperature"] = temperature
        if seed is not None:
            chat_kwargs["seed"] = seed

        file_results: list[dict[str, Any]] = []
        repaired_files: list[str] = []

        for target_file, diagnostics in diagnostics_by_file.items():
            current_code = repaired_code_by_file.get(target_file, "")
            ast_context = [
                location.to_dict()
                for location in ast_service.describe_locations(
                    target_file,
                    current_code,
                    [
                        diagnostic["line"]
                        for diagnostic in diagnostics
                        if diagnostic.get("line")
                    ],
                    max_locations=max_ast_locations,
                )
            ]

            file_result: dict[str, Any] = {
                "target_file": target_file,
                "diagnostic_count": len(diagnostics),
                "ast_context_available": any(
                    entry.get("available") for entry in ast_context
                ),
                "changed": False,
                "chunked_mode": len(current_code) > max_single_shot_code_chars,
            }

            # Diagnostics routinely name a symbol declared in a file the model
            # never sees, which is how a repair loop can keep reproducing the
            # same "does not implement inherited abstract member" error. These
            # declarations are read-only context: they must not be edited.
            related_symbols: list[dict[str, Any]] = []
            if repo_path:
                try:
                    related_symbols = [
                        context.to_dict()
                        for context in symbol_context_service.resolve(
                            repo_path,
                            [
                                str(diagnostic.get("message") or "")
                                for diagnostic in diagnostics
                            ],
                            exclude_files=repaired_code_by_file.keys(),
                            max_symbols=max_related_symbols,
                            max_files=max_related_symbol_files,
                            max_declarations=max_related_declarations,
                        )
                    ]
                except Exception as error:  # pragma: no cover - defensive
                    file_result["related_symbols_error"] = str(error)
            file_result["related_symbol_files"] = [
                context["file"] for context in related_symbols
            ]

            # The repository resolver deliberately skips files whose content is
            # already in the prompt, so the contract imposed by a callee
            # declared in the failing file itself was never shown. Chunked
            # repair makes that gap decisive, because the declaration can sit in
            # a chunk the model is not being given.
            semantic_context: list[dict[str, Any]] = []
            try:
                semantic_context = [
                    context.to_dict()
                    for context in semantic_service.describe(
                        target_file,
                        current_code,
                        diagnostics,
                        repo_path=repo_path,
                        symbol_resolver=symbol_context_service
                        if repo_path
                        else None,
                        exclude_files=repaired_code_by_file.keys(),
                        max_diagnostics=max_semantic_diagnostics,
                    )
                ]
            except Exception as error:  # pragma: no cover - defensive
                file_result["semantic_context_error"] = str(error)
            file_result["semantic_context_resolved_symbols"] = [
                symbol["symbol"]
                for context in semantic_context
                for symbol in context.get("symbols", [])
                if symbol.get("origin") != "external_or_unresolved"
            ]

            try:
                if file_result["chunked_mode"]:
                    chunks = ApplyPlanSweCodeChangeTool._split_code_chunks(
                        current_code,
                        chunk_lines=chunk_lines,
                    )
                    selected_chunks = self._select_repair_chunks(
                        chunks,
                        diagnostics,
                        problem_summary,
                        max_chunks=max_build_repair_chunks,
                    )
                    repaired_chunks: dict[int, str] = {}
                    chunk_results: list[dict[str, Any]] = []
                    prompts: list[str] = []
                    raw_responses: list[str] = []

                    for chunk in selected_chunks:
                        prompt = self._build_chunk_repair_prompt(
                            problem_summary=problem_summary,
                            target_path=target_file,
                            chunk=chunk,
                            total_chunks=len(chunks),
                            diagnostics=diagnostics,
                            repair_history=recent_repair_history,
                            ast_context=ast_context,
                            semantic_context=semantic_context,
                            related_symbols=related_symbols,
                            build_command=build_command,
                            build_output_tail=build_output_tail,
                            attempt=attempt,
                            max_attempts=max_attempts,
                            template_service=template_service,
                        )
                        raw_response = llm_client.chat(prompt, **chat_kwargs)
                        prompts.append(prompt)
                        raw_responses.append(raw_response)
                        chunk_result = {
                            key: chunk[key]
                            for key in (
                                "index",
                                "start",
                                "end",
                                "positioned_diagnostic_lines",
                                "lexical_score",
                                "selection_reason",
                            )
                        }
                        chunk_result["prompt"] = prompt
                        chunk_result["raw_response"] = raw_response

                        blocks = ApplyPlanSweCodeChangeTool._extract_code_blocks(
                            raw_response
                        )
                        if not raw_response.strip() or not blocks:
                            chunk_result["rejected_reason"] = (
                                "Chunk repair returned no complete fenced chunk."
                            )
                            chunk_results.append(chunk_result)
                            continue
                        repaired_chunk = (
                            ApplyPlanSweCodeChangeTool._select_generated_code(
                                str(chunk["code"]),
                                blocks,
                                raw_response,
                            )
                        )
                        repaired_chunk = (
                            ApplyPlanSweCodeChangeTool._normalize_generated_formatting(
                                original_code=str(chunk["code"]),
                                generated_code=repaired_chunk,
                            )
                        )
                        repaired_chunk = ApplyPlanSweCodeChangeTool._strip_transport_bom(
                            repaired_chunk
                        )
                        if not repaired_chunk.strip():
                            chunk_result["rejected_reason"] = (
                                "Chunk repair returned empty content."
                            )
                        elif self._is_destructively_truncated(
                            str(chunk["code"]),
                            repaired_chunk,
                        ):
                            chunk_result["rejected_reason"] = (
                                "Chunk repair was destructively truncated and was discarded."
                            )
                        else:
                            repaired_chunks[int(chunk["index"])] = repaired_chunk
                            chunk_result["changed"] = (
                                repaired_chunk.strip() != str(chunk["code"]).strip()
                            )
                        chunk_results.append(chunk_result)

                    repaired_code = self._merge_repaired_chunks(
                        chunks,
                        repaired_chunks,
                        final_newline=current_code.endswith(("\n", "\r")),
                    )
                    file_result["selected_chunks"] = chunk_results
                    file_result["chunk_count"] = len(chunks)
                    file_result["chunk_line_size"] = chunk_lines
                    file_result["prompt"] = "\n\n".join(prompts)
                    file_result["raw_response"] = "\n\n".join(raw_responses)

                    validation = validator.validate(
                        target_file,
                        repaired_code,
                        max_diagnostics=max_syntax_diagnostics,
                    )
                    file_result["syntax_validation"] = validation.to_dict()
                    if validation.available and not validation.valid:
                        file_result["rejected_reason"] = (
                            "Reconstructed chunk repair introduced invalid syntax "
                            "and was discarded."
                        )
                    elif repaired_code.strip() == current_code.strip():
                        rejected_chunks = [
                            chunk
                            for chunk in chunk_results
                            if chunk.get("rejected_reason")
                        ]
                        file_result["rejected_reason"] = (
                            rejected_chunks[0]["rejected_reason"]
                            if rejected_chunks
                            else "Repair returned unchanged content."
                        )
                    else:
                        repaired_code_by_file[target_file] = repaired_code
                        repaired_files.append(target_file)
                        file_result["changed"] = True
                    file_results.append(file_result)
                    continue

                prompt = self._build_repair_prompt(
                    problem_summary=problem_summary,
                    target_path=target_file,
                    current_code=current_code,
                    diagnostics=diagnostics,
                    repair_history=recent_repair_history,
                    ast_context=ast_context,
                    semantic_context=semantic_context,
                    related_symbols=related_symbols,
                    build_command=build_command,
                    build_output_tail=build_output_tail,
                    attempt=attempt,
                    max_attempts=max_attempts,
                    template_service=template_service,
                )
                file_result["prompt"] = prompt
                raw_response = llm_client.chat(prompt, **chat_kwargs)
                file_result["raw_response"] = raw_response

                blocks = ApplyPlanSweCodeChangeTool._extract_code_blocks(raw_response)
                repaired_code = ApplyPlanSweCodeChangeTool._select_generated_code(
                    current_code, blocks, raw_response
                )
                repaired_code = (
                    ApplyPlanSweCodeChangeTool._normalize_generated_formatting(
                        original_code=current_code,
                        generated_code=repaired_code,
                    )
                )
                repaired_code = ApplyPlanSweCodeChangeTool._strip_transport_bom(
                    repaired_code
                )

                validation = validator.validate(
                    target_file,
                    repaired_code,
                    max_diagnostics=max_syntax_diagnostics,
                )
                file_result["syntax_validation"] = validation.to_dict()

                if not repaired_code.strip():
                    file_result["rejected_reason"] = "Repair returned empty content."
                elif validation.available and not validation.valid:
                    # A syntactically broken repair would replace a semantic
                    # error with a worse one, so the previous content is kept.
                    file_result["rejected_reason"] = (
                        "Repair introduced invalid syntax and was discarded."
                    )
                elif repaired_code.strip() == current_code.strip():
                    file_result["rejected_reason"] = (
                        "Repair returned unchanged content."
                    )
                else:
                    repaired_code_by_file[target_file] = repaired_code
                    repaired_files.append(target_file)
                    file_result["changed"] = True
            except Exception as exc:  # pragma: no cover - provider/runtime failures
                file_result["error"] = f"{type(exc).__name__}: {exc}"
                self._registry._logger.warning(
                    "repair_build_failure failed for %s: %s", target_file, exc
                )

            file_results.append(file_result)

        result["file_results"] = file_results
        result["repaired_files"] = repaired_files
        result["generated_code_by_file"] = repaired_code_by_file
        result["changed"] = bool(repaired_files)
        return result
