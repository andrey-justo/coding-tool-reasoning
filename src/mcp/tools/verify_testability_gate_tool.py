from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from src.models.testability_gate import TestPassRateResult, VerifyTestabilityGateResult


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

    @classmethod
    def _run_command_with_timeout(
        cls,
        command: list[str],
        cwd: Path,
        timeout_seconds: int,
    ) -> dict[str, Any]:
        started = time.monotonic()
        try:
            completed = subprocess.run(
                command,
                cwd=str(cwd),
                text=True,
                capture_output=True,
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
    def _discover_verification_commands(
        repo_path: Path,
        junit_xml_path: Path,
        coverage_xml_path: Path,
    ) -> dict[str, Any]:
        pyproject = repo_path / "pyproject.toml"
        pytest_ini = repo_path / "pytest.ini"
        tests_dir = repo_path / "tests"
        src_dir = repo_path / "src"

        has_python_project = (
            pyproject.exists() or pytest_ini.exists() or tests_dir.exists()
        )
        has_pytest = shutil.which("pytest") is not None

        build_command: list[str] | None = None
        if has_python_project and src_dir.exists():
            build_command = [sys.executable, "-m", "compileall", "-q", "src"]

        test_command: list[str] | None = None
        if has_python_project and (
            has_pytest or pytest_ini.exists() or tests_dir.exists()
        ):
            test_command = [
                sys.executable,
                "-m",
                "pytest",
                "--maxfail=1",
                "--disable-warnings",
                f"--junitxml={junit_xml_path.as_posix()}",
                f"--cov-report=xml:{coverage_xml_path.as_posix()}",
                "--cov=src",
            ]

        return {
            "project_type": "python" if has_python_project else "unknown",
            "build_command": build_command,
            "test_command": test_command,
        }

    def execute(
        self,
        repo_path: str,
        base_ref: str,
        generated_code_by_file: dict[str, str],
        timeout_seconds: int = 300,
    ) -> dict[str, Any]:
        """Run build/test validation in a detached worktree with generated file contents."""

        resolved_repo_path = Path(repo_path).resolve()
        gate_result = VerifyTestabilityGateResult()

        with tempfile.TemporaryDirectory(prefix="issue-mcp-gate-") as temp_dir:
            worktree_path = Path(temp_dir)
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
                check=False,
            )
            if setup_result.returncode != 0:
                reason = (
                    "Could not create temporary worktree for verification gate: "
                    f"{self._tail_text(setup_result.stderr) or self._tail_text(setup_result.stdout)}"
                )
                gate_result.testability_gate.reason = reason
                gate_result.log_lines.append(reason)
                return gate_result.to_dict()

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
                )

                build_command = discovery.get("build_command")
                test_command = discovery.get("test_command")

                if isinstance(build_command, list):
                    gate_result.build.command = build_command
                    gate_result.log_lines.append(
                        "Verification gate build command discovered: "
                        + " ".join(build_command)
                    )
                    build_execution = self._run_command_with_timeout(
                        build_command,
                        cwd=worktree_path,
                        timeout_seconds=timeout_seconds,
                    )
                    gate_result.build.status = str(build_execution.get("status", "not-run"))
                    gate_result.build.exit_code = build_execution.get("exit_code")
                    gate_result.build.duration_seconds = build_execution.get(
                        "duration_seconds"
                    )
                    gate_result.build.stdout_tail = build_execution.get("stdout_tail")
                    gate_result.build.stderr_tail = build_execution.get("stderr_tail")
                    gate_result.build.timed_out = build_execution.get("timed_out")

                if isinstance(test_command, list):
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
                    gate_result.test.status = str(test_execution.get("status", "not-run"))
                    gate_result.test.exit_code = test_execution.get("exit_code")
                    gate_result.test.duration_seconds = test_execution.get(
                        "duration_seconds"
                    )
                    gate_result.test.stdout_tail = test_execution.get("stdout_tail")
                    gate_result.test.stderr_tail = test_execution.get("stderr_tail")
                    gate_result.test.timed_out = test_execution.get("timed_out")

                junit_totals = self._parse_junit_totals(junit_xml_path)
                if junit_totals is not None:
                    tests = int(junit_totals.get("tests", 0))
                    failures = int(junit_totals.get("failures", 0))
                    errors = int(junit_totals.get("errors", 0))
                    passed = int(junit_totals.get("passed", 0))
                    rate = (passed / tests) if tests > 0 else 0.0
                    gate_result.junit.available = True
                    gate_result.junit.path = str(junit_xml_path)
                    gate_result.junit.totals = junit_totals
                    gate_result.test_pass_rate_source = "junit_xml"
                    gate_result.test_pass_rate = TestPassRateResult(
                        rate=rate,
                        total=tests,
                        passed=passed,
                        failures=failures,
                        errors=errors,
                    )

                if coverage_xml_path.exists():
                    gate_result.coverage.available = True
                    gate_result.coverage.path = str(coverage_xml_path)

                build_status = gate_result.build.status
                test_status = gate_result.test.status
                if build_status == "pass" and test_status == "pass":
                    reason = (
                        "Build and tests passed in generated-code verification worktree."
                    )
                elif test_status in {"fail", "timeout"}:
                    reason = (
                        "Tests failed or timed out in generated-code verification worktree."
                    )
                elif build_status in {"fail", "timeout"}:
                    reason = (
                        "Build failed or timed out in generated-code verification worktree."
                    )
                elif build_status == "not-run" and test_status == "not-run":
                    reason = "No build/test command discovered for this repository."
                else:
                    reason = "Verification gate completed with partial execution."

                gate_result.testability_gate.build_status = build_status
                gate_result.testability_gate.test_status = test_status
                gate_result.testability_gate.reason = reason
                gate_result.log_lines.append(
                    "Verification gate result: "
                    f"build={build_status}, test={test_status}, reason={reason}"
                )
                return gate_result.to_dict()
            finally:
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
                    check=False,
                )
