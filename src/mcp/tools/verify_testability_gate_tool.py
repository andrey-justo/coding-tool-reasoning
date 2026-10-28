from __future__ import annotations

import logging
import json
import shutil
import subprocess
import tempfile
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from src.models.testability_gate import TestPassRateResult, VerifyTestabilityGateResult
from src.service.build_diagnostics import (
    BuildDiagnosticContext,
    BuildDiagnosticParserResolver,
)
from src.service.code_sanitization import (
    VerificationContext,
    VerificationStrategyResolver,
)
from src.service.language_detection import infer_language_from_file_paths
from src.service.ast_context_service import AstContextService, declaration_signature_at

_GIT_SETUP_TIMEOUT_SECONDS = 600
logger = logging.getLogger(__name__)


class VerifyTestabilityGateTool:
    """Run build/test validation for generated code in an isolated git worktree."""

    def __init__(self, registry) -> None:
        self._registry = registry

    @staticmethod
    def _tail_text(text: str | None, lines: int = 20) -> str:
        if not text:
            return ""
        chunks = text.splitlines()
        return "\n".join(chunks[-lines:])

    @staticmethod
    def _preserve_artifact(artifact_path: Path, log_lines: list[str]) -> str:
        """Copy a verification artifact out of the disposable worktree.

        The worktree is deleted as soon as the gate returns, so downstream
        consumers such as the test repair loop would otherwise receive a path
        that no longer exists.
        """

        try:
            preserved_dir = Path(tempfile.mkdtemp(prefix="issue-mcp-gate-artifacts-"))
            preserved_path = preserved_dir / artifact_path.name
            shutil.copy2(artifact_path, preserved_path)
            return str(preserved_path)
        except OSError as exc:
            log_lines.append(
                f"Could not preserve verification artifact {artifact_path.name}: {exc}"
            )
            return str(artifact_path)

    @staticmethod
    def _parse_junit_totals(junit_xml_path: Path) -> dict[str, int] | None:
        if not junit_xml_path.exists():
            return None
        try:
            root = ET.parse(junit_xml_path).getroot()
        except ET.ParseError:
            return None

        if root.tag == "testsuite":
            tests = int(root.attrib.get("tests", 0))
            failures = int(root.attrib.get("failures", 0))
            errors = int(root.attrib.get("errors", 0))
            skipped = int(root.attrib.get("skipped", 0))
            return {
                "tests": tests,
                "failures": failures,
                "errors": errors,
                "skipped": skipped,
                "passed": max(tests - failures - errors - skipped, 0),
            }

        if root.tag == "testsuites":
            tests = failures = errors = skipped = 0
            for suite in root.findall("testsuite"):
                tests += int(suite.attrib.get("tests", 0))
                failures += int(suite.attrib.get("failures", 0))
                errors += int(suite.attrib.get("errors", 0))
                skipped += int(suite.attrib.get("skipped", 0))
            return {
                "tests": tests,
                "failures": failures,
                "errors": errors,
                "skipped": skipped,
                "passed": max(tests - failures - errors - skipped, 0),
            }

        return None

    @staticmethod
    def _parse_trx_totals(trx_path: Path) -> dict[str, int] | None:
        """Parse a VSTest TRX result summary into JUnit-shaped totals.

        The dotnet strategy emits TRX rather than JUnit XML, so without this the
        gate would report a pass/fail verdict from the exit code while leaving
        the structured test metrics empty.
        """

        if not trx_path.exists():
            return None
        try:
            root = ET.parse(trx_path).getroot()
        except ET.ParseError:
            return None

        counters = next(
            (
                element
                for element in root.iter()
                if element.tag.rsplit("}", 1)[-1] == "Counters"
            ),
            None,
        )
        if counters is None:
            return None

        def attr(name: str) -> int:
            try:
                return int(counters.attrib.get(name, 0))
            except ValueError:
                return 0

        total = attr("total")
        failures = attr("failed")
        errors = attr("error") + attr("aborted") + attr("timeout")
        passed = attr("passed")
        skipped = max(total - attr("executed"), 0)
        return {
            "tests": total,
            "failures": failures,
            "errors": errors,
            "skipped": skipped,
            "passed": passed,
        }

    @classmethod
    def _run_command_with_timeout(
        cls,
        command: list[str],
        cwd: Path,
        timeout_seconds: float,
    ) -> dict[str, Any]:
        started = time.monotonic()
        try:
            completed = subprocess.run(
                command,
                cwd=str(cwd),
                text=True,
                capture_output=True,
                stdin=subprocess.DEVNULL,
                timeout=timeout_seconds,
                check=False,
            )
            duration = time.monotonic() - started
            return {
                "status": "pass" if completed.returncode == 0 else "fail",
                "exit_code": completed.returncode,
                "duration_seconds": round(duration, 3),
                "stdout_tail": cls._tail_text(completed.stdout),
                "stderr_tail": cls._tail_text(completed.stderr),
                "timed_out": False,
                "stdout": completed.stdout,
                "stderr": completed.stderr,
            }
        except subprocess.TimeoutExpired as exc:
            duration = time.monotonic() - started
            return {
                "status": "timeout",
                "exit_code": None,
                "duration_seconds": round(duration, 3),
                "stdout_tail": cls._tail_text(
                    exc.stdout if isinstance(exc.stdout, str) else ""
                ),
                "stderr_tail": cls._tail_text(
                    exc.stderr if isinstance(exc.stderr, str) else ""
                ),
                "timed_out": True,
            }

    @staticmethod
    def _capture_build_diagnostics(
        execution: dict[str, Any],
        worktree: Path,
        project_type: str,
        changed_files: list[str],
    ) -> list[dict[str, Any]]:
        output = "\n".join(
            str(execution.get(key) or "")
            for key in ("stdout", "stderr", "stdout_tail", "stderr_tail")
        )
        parsed = BuildDiagnosticParserResolver().parse(
            output,
            BuildDiagnosticContext(
                project_type=project_type,
                language=infer_language_from_file_paths(changed_files),
                changed_files=tuple(changed_files),
            ),
            max_diagnostics=100,
        )
        diagnostics = [diagnostic.to_dict() for diagnostic in parsed.errors]
        remaining_chars = 12000
        root = worktree.resolve()
        inventoried: set[Path] = set()
        for diagnostic in diagnostics:
            file = diagnostic.get("file")
            line = diagnostic.get("line")
            if not file:
                continue
            source = (root / file).resolve()
            if not source.is_relative_to(root):
                continue
            diagnostic["relative_file"] = source.relative_to(root).as_posix()
            if not line or remaining_chars <= 0:
                continue
            if not source.is_file():
                diagnostic["source_context_error"] = (
                    "Diagnostic source was not materialized in the verification worktree."
                )
                continue
            try:
                source_text = source.read_text(encoding="utf-8-sig")
                lines = source_text.splitlines()
            except (OSError, UnicodeError) as error:
                diagnostic["source_context_error"] = str(error)
                continue
            start = max(0, int(line) - 9)
            excerpt = "\n".join(
                f"{index + 1}: {lines[index]}"
                for index in range(start, min(len(lines), int(line) + 8))
            )[: min(2000, remaining_chars)]
            diagnostic["source_excerpt"] = excerpt
            remaining_chars -= len(excerpt)
            if source not in inventoried and (
                source.name.endswith(".g.cs") or "obj" in source.relative_to(root).parts
            ):
                inventoried.add(source)
                outline = AstContextService().describe_outline(
                    source.name,
                    source_text,
                    max_declarations=80,
                )
                inventory = []
                budget = min(4000, remaining_chars)
                for declaration in outline.declarations:
                    entry = {
                        "name": declaration.name,
                        "line": declaration.start_line,
                        "signature": declaration_signature_at(
                            lines, declaration.start_line
                        )[:400],
                    }
                    cost = len(json.dumps(entry))
                    if cost > budget:
                        break
                    inventory.append(entry)
                    budget -= cost
                    remaining_chars -= cost
                diagnostic["generated_declarations"] = inventory
                diagnostic["generated_declarations_truncated"] = (
                    len(inventory) < len(outline.declarations)
                    or len(outline.declarations) >= 80
                )
                if outline.error:
                    diagnostic["generated_outline_error"] = outline.error
        return diagnostics

    @staticmethod
    def _discover_verification_commands(
        repo_path: Path,
        junit_xml_path: Path,
        coverage_xml_path: Path,
        changed_files: list[str] | None = None,
        verification_config: Any = None,
    ) -> dict[str, Any]:
        changed = tuple(changed_files or ())
        context = VerificationContext(
            repo_path=repo_path,
            junit_xml_path=junit_xml_path,
            coverage_xml_path=coverage_xml_path,
            changed_files=changed,
            language=infer_language_from_file_paths(list(changed)),
        )
        resolver = VerificationStrategyResolver(config=verification_config)
        return resolver.resolve(context).to_dict()

    def _load_verification_config(self) -> Any:
        try:
            return self._registry._create_swe_server_context().config.verification
        except Exception:  # pragma: no cover - defensive for minimal registries
            return None

    def execute(
        self,
        repo_path: str,
        base_ref: str,
        generated_code_by_file: dict[str, str],
        timeout_seconds: int = 300,
        focus_files: list[str] | None = None,
        compile_only: bool = False,
    ) -> dict[str, Any]:
        """Run build/test validation in a detached worktree with generated file contents."""

        resolved_repo_path = Path(repo_path).resolve()
        if focus_files is not None and (
            not focus_files or not set(focus_files) <= generated_code_by_file.keys()
        ):
            raise ValueError(
                "Focused verification requires nonempty files from the candidate."
            )
        gate_result = VerifyTestabilityGateResult()

        def serialize_result() -> dict[str, Any]:
            result = gate_result.to_dict()
            result.update(
                verification_scope="focused" if focus_files is not None else "full",
                focus_files=focus_files,
                compile_only=compile_only,
            )
            return result

        # Worktree setup/teardown is bounded separately: it should never take as
        # long as a full build, and an unbounded call here blocks the pipeline.
        git_timeout_seconds = min(timeout_seconds, _GIT_SETUP_TIMEOUT_SECONDS)

        with tempfile.TemporaryDirectory(prefix="issue-mcp-gate-") as temp_dir:
            worktree_path = Path(temp_dir)
            try:
                setup_result = subprocess.run(
                    [
                        "git",
                        "-C",
                        str(resolved_repo_path),
                        "worktree",
                        "add",
                        "--detach",
                        str(worktree_path),
                        base_ref,
                    ],
                    text=True,
                    capture_output=True,
                    stdin=subprocess.DEVNULL,
                    timeout=git_timeout_seconds,
                    check=False,
                )
            except subprocess.TimeoutExpired:
                reason = (
                    "Timed out creating temporary worktree for verification gate after "
                    f"{git_timeout_seconds}s."
                )
                gate_result.testability_gate.reason = reason
                gate_result.log_lines.append(reason)
                return serialize_result()

            if setup_result.returncode != 0:
                reason = (
                    "Could not create temporary worktree for verification gate: "
                    f"{self._tail_text(setup_result.stderr) or self._tail_text(setup_result.stdout)}"
                )
                gate_result.testability_gate.reason = reason
                gate_result.log_lines.append(reason)
                return serialize_result()

            try:
                for relative_path, content in generated_code_by_file.items():
                    file_path = worktree_path / relative_path
                    file_path.parent.mkdir(parents=True, exist_ok=True)
                    file_path.write_text(content, encoding="utf-8")

                artifacts_dir = worktree_path / ".experiment_artifacts"
                artifacts_dir.mkdir(parents=True, exist_ok=True)
                junit_xml_path = artifacts_dir / "junit.xml"
                coverage_xml_path = artifacts_dir / "coverage.xml"

                discovery = self._discover_verification_commands(
                    repo_path=worktree_path,
                    junit_xml_path=junit_xml_path,
                    coverage_xml_path=coverage_xml_path,
                    changed_files=focus_files
                    if focus_files is not None
                    else list(generated_code_by_file),
                    verification_config=self._load_verification_config(),
                )

                build_command = discovery.get("build_command")
                test_command = discovery.get("test_command")

                if isinstance(build_command, list):
                    stages = [
                        ("prerequisite", command)
                        for command in discovery.get("pre_build_commands", [])
                    ] + [("full", build_command)]
                    build_started = time.monotonic()
                    for stage, command in stages:
                        gate_result.build.command = command
                        gate_result.build.stage = stage
                        gate_result.log_lines.append(
                            f"Verification gate {stage} build: " + " ".join(command)
                        )
                        logger.info(
                            "Verification build stage %s: %s", stage, " ".join(command)
                        )
                        remaining_seconds = max(
                            0.001, timeout_seconds - (time.monotonic() - build_started)
                        )
                        execution = self._run_command_with_timeout(
                            command,
                            cwd=worktree_path,
                            timeout_seconds=remaining_seconds,
                        )
                        gate_result.build.status = str(
                            execution.get("status", "not-run")
                        )
                        gate_result.build.exit_code = execution.get("exit_code")
                        gate_result.build.duration_seconds = execution.get(
                            "duration_seconds"
                        )
                        gate_result.build.stdout_tail = execution.get("stdout_tail")
                        gate_result.build.stderr_tail = execution.get("stderr_tail")
                        gate_result.build.timed_out = execution.get("timed_out")
                        gate_result.build.diagnostics = self._capture_build_diagnostics(
                            execution,
                            worktree_path,
                            discovery.get("project_type", "unknown"),
                            list(generated_code_by_file),
                        )
                        gate_result.build.stages.append(
                            {
                                "stage": stage,
                                "command": command,
                                "status": gate_result.build.status,
                                "duration_seconds": gate_result.build.duration_seconds,
                            }
                        )
                        logger.info(
                            "Verification build stage %s finished: %s (%.3fs)",
                            stage,
                            gate_result.build.status,
                            gate_result.build.duration_seconds or 0.0,
                        )
                        if gate_result.build.status != "pass":
                            break
                        gate_result.build.completed_stages += 1
                    if all(
                        entry["duration_seconds"] is not None
                        for entry in gate_result.build.stages
                    ):
                        gate_result.build.duration_seconds = round(
                            sum(
                                entry["duration_seconds"]
                                for entry in gate_result.build.stages
                            ),
                            3,
                        )

                if (
                    not compile_only
                    and isinstance(test_command, list)
                    and gate_result.build.status
                    in {
                        "pass",
                        "not-run",
                    }
                ):
                    gate_result.test.command = test_command
                    gate_result.log_lines.append(
                        "Verification gate test command discovered: "
                        + " ".join(test_command)
                    )
                    test_execution = self._run_command_with_timeout(
                        test_command,
                        cwd=worktree_path,
                        timeout_seconds=timeout_seconds,
                    )
                    gate_result.test.status = str(
                        test_execution.get("status", "not-run")
                    )
                    gate_result.test.exit_code = test_execution.get("exit_code")
                    gate_result.test.duration_seconds = test_execution.get(
                        "duration_seconds"
                    )
                    gate_result.test.stdout_tail = test_execution.get("stdout_tail")
                    gate_result.test.stderr_tail = test_execution.get("stderr_tail")
                    gate_result.test.timed_out = test_execution.get("timed_out")

                junit_totals = self._parse_junit_totals(junit_xml_path)
                results_path = junit_xml_path
                results_source = "junit_xml"
                if junit_totals is None:
                    trx_path = junit_xml_path.with_suffix(".trx")
                    junit_totals = self._parse_trx_totals(trx_path)
                    if junit_totals is not None:
                        results_path = trx_path
                        results_source = "trx"
                if junit_totals is not None:
                    tests = int(junit_totals.get("tests", 0))
                    failures = int(junit_totals.get("failures", 0))
                    errors = int(junit_totals.get("errors", 0))
                    passed = int(junit_totals.get("passed", 0))
                    rate = (passed / tests) if tests > 0 else 0.0
                    gate_result.junit.available = True
                    gate_result.junit.path = self._preserve_artifact(
                        results_path, gate_result.log_lines
                    )
                    gate_result.junit.totals = junit_totals
                    gate_result.test_pass_rate_source = results_source
                    gate_result.test_pass_rate = TestPassRateResult(
                        rate=rate,
                        total=tests,
                        passed=passed,
                        failures=failures,
                        errors=errors,
                    )

                if coverage_xml_path.exists():
                    gate_result.coverage.available = True
                    gate_result.coverage.path = self._preserve_artifact(
                        coverage_xml_path, gate_result.log_lines
                    )

                build_status = gate_result.build.status
                test_status = gate_result.test.status
                if build_status == "pass" and test_status == "pass":
                    reason = "Build and tests passed in generated-code verification worktree."
                elif test_status in {"fail", "timeout"}:
                    reason = "Tests failed or timed out in generated-code verification worktree."
                elif build_status in {"fail", "timeout"}:
                    reason = "Build failed or timed out in generated-code verification worktree."
                elif build_status == "not-run" and test_status == "not-run":
                    reason = "No build/test command discovered for this repository."
                else:
                    reason = "Verification gate completed with partial execution."

                gate_result.testability_gate.build_status = build_status
                gate_result.testability_gate.test_status = test_status
                if compile_only and build_status == "pass":
                    reason = "Compilation-only checkpoint passed; full verification is still required."
                gate_result.testability_gate.reason = reason
                gate_result.log_lines.append(
                    "Verification gate result: "
                    f"build={build_status}, test={test_status}, reason={reason}"
                )
                return serialize_result()
            finally:
                try:
                    subprocess.run(
                        [
                            "git",
                            "-C",
                            str(resolved_repo_path),
                            "worktree",
                            "remove",
                            "--force",
                            str(worktree_path),
                        ],
                        text=True,
                        capture_output=True,
                        stdin=subprocess.DEVNULL,
                        timeout=git_timeout_seconds,
                        check=False,
                    )
                except subprocess.TimeoutExpired:
                    gate_result.log_lines.append(
                        "Timed out removing temporary verification worktree."
                    )
