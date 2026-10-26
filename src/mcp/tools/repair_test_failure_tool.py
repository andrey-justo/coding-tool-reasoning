from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.llm_client.multi_model_llm_client import MultiModelLLMClient
from src.mcp.tools.apply_plan_swe_code_change_tool import ApplyPlanSweCodeChangeTool
from src.service.ast_context_service import AstContextService
from src.service.build_diagnostics import match_diagnostic_file
from src.service.language_detection import infer_language_from_file_paths
from src.service.symbol_context_service import RepositorySymbolContextService
from src.service.syntax_validator import SyntaxValidator
from src.service.test_diagnostics import (
    TestFailureContext,
    TestFailureParserResolver,
)
from src.service.tool_prompt_template_service import ToolPromptTemplateService

TEST_REPAIR_TEMPLATE_NAME = "test_repair"

_TEST_FILE_MARKERS = ("test", "spec")


class RepairTestFailureTool:
    """Repair failing tests using structured test results and AST context.

    A successful build only proves the generated code compiles; it says nothing
    about behavior. This tool closes that gap by feeding parsed test failures,
    the enclosing AST declarations and a cross-file declaration index back to
    the model, so a failing assertion can be fixed at its real cause.
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
    def _is_test_file(target_file: str) -> bool:
        name = Path(target_file.replace("\\", "/")).name.lower()
        return any(marker in name for marker in _TEST_FILE_MARKERS)

    @classmethod
    def _select_repair_targets(
        cls,
        failures_by_file: dict[str, list[dict[str, Any]]],
        generated_code_by_file: dict[str, str],
        *,
        max_files: int,
    ) -> list[str]:
        """Order the files worth repairing for the current failures.

        Files named by a stack trace come first, but a failing assertion inside
        a test file is usually caused by production code, so the non-test files
        changed in the same task are appended as secondary candidates instead of
        letting the model rewrite the test to make it pass.
        """

        targets: list[str] = [
            target_file
            for target_file in failures_by_file
            if not cls._is_test_file(target_file)
        ]
        targets.extend(
            target_file
            for target_file in failures_by_file
            if cls._is_test_file(target_file)
        )

        if not any(not cls._is_test_file(target) for target in targets):
            targets = [
                target_file
                for target_file in generated_code_by_file
                if not cls._is_test_file(target_file)
            ] + targets

        ordered = list(dict.fromkeys(targets))
        return ordered[: max(int(max_files), 1)]

    @staticmethod
    def _build_repair_prompt(
        *,
        problem_summary: str,
        target_path: str,
        current_code: str,
        failures: list[dict[str, Any]],
        failures_parser: str,
        ast_context: list[dict[str, Any]],
        related_files: list[dict[str, Any]],
        related_symbols: list[dict[str, Any]],
        test_command: list[str] | None,
        test_output_tail: str,
        attempt: int,
        max_attempts: int,
        template_service: ToolPromptTemplateService,
    ) -> str:
        return template_service.render(
            TEST_REPAIR_TEMPLATE_NAME,
            {
                "PROBLEM_SUMMARY": problem_summary.strip()
                or "[no problem summary provided]",
                "TARGET_PATH": target_path,
                "ATTEMPT": str(attempt),
                "MAX_ATTEMPTS": str(max_attempts),
                "TEST_COMMAND": " ".join(test_command) if test_command else "n/a",
                "FAILURES_PARSER": failures_parser,
                "FAILURES_JSON": json.dumps(failures, ensure_ascii=False, indent=2),
                "AST_CONTEXT_JSON": json.dumps(
                    ast_context, ensure_ascii=False, indent=2
                ),
                "RELATED_FILES_JSON": json.dumps(
                    related_files, ensure_ascii=False, indent=2
                ),
                "RELATED_SYMBOLS_JSON": json.dumps(
                    related_symbols, ensure_ascii=False, indent=2
                ),
                "TEST_OUTPUT_TAIL": test_output_tail,
                "CURRENT_CODE": current_code,
            },
        )

    def execute(
        self,
        problem_summary: str,
        test_output: str,
        generated_code_by_file: dict[str, str],
        results_path: str | None = None,
        test_command: list[str] | None = None,
        attempt: int = 1,
        max_attempts: int = 10,
        temperature: float | None = None,
        seed: int | None = None,
        repo_path: str | None = None,
    ) -> dict[str, Any]:
        """Produce repaired file contents for the files explaining the failures."""

        config = self._execution_config()
        max_failures = int(getattr(config, "max_test_failures", 10) or 10)
        max_output_chars = int(getattr(config, "max_test_output_chars", 6000) or 6000)
        max_ast_locations = int(getattr(config, "max_test_ast_locations", 5) or 5)
        max_repair_files = int(getattr(config, "max_test_repair_files", 3) or 3)
        max_related = int(getattr(config, "max_test_related_declarations", 40) or 40)
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

        repaired_code_by_file = dict(generated_code_by_file)
        resolved_results_path = Path(results_path) if results_path else None
        failures_result = TestFailureParserResolver().parse(
            TestFailureContext(
                output=test_output or "",
                results_path=resolved_results_path,
                language=infer_language_from_file_paths(list(generated_code_by_file)),
                project_type=self._verification_project_type(),
                changed_files=tuple(generated_code_by_file),
            ),
            max_failures=max_failures,
        )

        failures_by_file: dict[str, list[dict[str, Any]]] = {}
        unmatched: list[dict[str, Any]] = []
        for failure in failures_result.failures:
            target_file = match_diagnostic_file(
                failure.file, generated_code_by_file.keys()
            )
            if target_file is None:
                unmatched.append(failure.to_dict())
                continue
            failures_by_file.setdefault(target_file, []).append(failure.to_dict())

        result: dict[str, Any] = {
            "attempt": int(attempt),
            "max_attempts": int(max_attempts),
            "failures_parser": failures_result.parser,
            "failures_by_file": failures_by_file,
            "unmatched_failures": unmatched,
            "generated_code_by_file": repaired_code_by_file,
            "file_results": [],
            "repaired_files": [],
            "changed": False,
        }

        if not failures_result.failures:
            result["error"] = (
                "No test failures could be parsed from the test results; "
                "automated test repair cannot target a file."
            )
            return result

        targets = self._select_repair_targets(
            failures_by_file, generated_code_by_file, max_files=max_repair_files
        )
        if not targets:
            result["error"] = (
                "No generated file could be associated with the failing tests."
            )
            return result
        result["repair_targets"] = targets

        llm_cls = self._registry._llm_client_cls or MultiModelLLMClient
        llm_client = llm_cls()
        template_service = self._template_service()
        validator = SyntaxValidator()
        ast_service = AstContextService()
        symbol_context_service = RepositorySymbolContextService()
        test_output_tail = self._tail(test_output or "", max_output_chars)
        all_failures = [failure.to_dict() for failure in failures_result.failures]

        chat_kwargs: dict[str, Any] = {}
        if temperature is not None:
            chat_kwargs["temperature"] = temperature
        if seed is not None:
            chat_kwargs["seed"] = seed

        file_results: list[dict[str, Any]] = []
        repaired_files: list[str] = []

        for target_file in targets:
            current_code = repaired_code_by_file.get(target_file, "")
            file_failures = failures_by_file.get(target_file) or []
            # Without a stack frame in this file the model still needs the whole
            # failure set to understand what behavior is missing.
            prompt_failures = file_failures or all_failures

            ast_context = [
                location.to_dict()
                for location in ast_service.describe_locations(
                    target_file,
                    current_code,
                    [
                        failure["line"]
                        for failure in file_failures
                        if failure.get("line")
                    ],
                    max_locations=max_ast_locations,
                )
            ]
            related_files = [
                ast_service.describe_outline(
                    related_path,
                    related_code,
                    max_declarations=max_related,
                ).to_dict()
                for related_path, related_code in repaired_code_by_file.items()
                if related_path != target_file
            ]

            # Failures frequently name a symbol declared outside the generated
            # set. These declarations are read-only context so the model stops
            # guessing signatures it cannot see.
            related_symbols: list[dict[str, Any]] = []
            if repo_path:
                try:
                    related_symbols = [
                        context.to_dict()
                        for context in symbol_context_service.resolve(
                            repo_path,
                            [
                                str(failure.get("message") or "")
                                + " "
                                + str(failure.get("details") or "")
                                for failure in prompt_failures
                            ],
                            exclude_files=repaired_code_by_file.keys(),
                            max_symbols=max_related_symbols,
                            max_files=max_related_symbol_files,
                            max_declarations=max_related_declarations,
                        )
                    ]
                except Exception as error:  # pragma: no cover - defensive
                    file_result_error = str(error)
                else:
                    file_result_error = None
            else:
                file_result_error = None

            file_result: dict[str, Any] = {
                "target_file": target_file,
                "failure_count": len(prompt_failures),
                "matched_by_stack_trace": bool(file_failures),
                "ast_context_available": any(
                    entry.get("available") for entry in ast_context
                ),
                "related_files": [entry["file"] for entry in related_files],
                "related_symbol_files": [
                    context["file"] for context in related_symbols
                ],
                "changed": False,
            }
            if file_result_error:
                file_result["related_symbols_error"] = file_result_error

            try:
                prompt = self._build_repair_prompt(
                    problem_summary=problem_summary,
                    target_path=target_file,
                    current_code=current_code,
                    failures=prompt_failures,
                    failures_parser=failures_result.parser,
                    ast_context=ast_context,
                    related_files=related_files,
                    related_symbols=related_symbols,
                    test_command=test_command,
                    test_output_tail=test_output_tail,
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
                    # A syntactically broken repair would trade a failing test
                    # for a failing build, so the previous content is kept.
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
                    "repair_test_failure failed for %s: %s", target_file, exc
                )

            file_results.append(file_result)

        result["file_results"] = file_results
        result["repaired_files"] = repaired_files
        result["generated_code_by_file"] = repaired_code_by_file
        result["changed"] = bool(repaired_files)
        return result
