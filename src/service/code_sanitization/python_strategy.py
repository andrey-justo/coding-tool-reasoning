from __future__ import annotations

import shutil
import sys
from typing import ClassVar

from src.service.code_sanitization.verification_strategy import (
    VerificationCommands,
    VerificationCommandStrategy,
    VerificationContext,
)


class PythonVerificationStrategy(VerificationCommandStrategy):
    """Discover compileall/pytest verification commands for Python repositories."""

    project_type: ClassVar[str] = "python"
    languages: ClassVar[frozenset[str]] = frozenset({"python"})

    def matches(self, context: VerificationContext) -> bool:
        repo_path = context.repo_path
        return (
            (repo_path / "pyproject.toml").exists()
            or (repo_path / "pytest.ini").exists()
            or (repo_path / "tests").exists()
        )

    def build(self, context: VerificationContext) -> VerificationCommands:
        repo_path = context.repo_path
        src_dir = repo_path / "src"
        pytest_ini = repo_path / "pytest.ini"
        tests_dir = repo_path / "tests"

        build_command: list[str] | None = None
        if src_dir.exists():
            build_command = [sys.executable, "-m", "compileall", "-q", "src"]

        test_command: list[str] | None = None
        has_pytest = shutil.which("pytest") is not None
        if has_pytest or pytest_ini.exists() or tests_dir.exists():
            test_command = [
                sys.executable,
                "-m",
                "pytest",
                "--maxfail=1",
                "--disable-warnings",
                f"--junitxml={context.junit_xml_path.as_posix()}",
                f"--cov-report=xml:{context.coverage_xml_path.as_posix()}",
                "--cov=src",
            ]

        return VerificationCommands(
            project_type=self.project_type,
            build_command=build_command,
            test_command=test_command,
        )
