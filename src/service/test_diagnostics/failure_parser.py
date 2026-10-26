"""Strategy-based parsing of test results into structured failures.

Parsers are selected from the structured result artifact produced by the
verification gate (TRX for .NET, JUnit XML for Python) and fall back to raw
runner output, mirroring how build diagnostics are parsed.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar, Sequence

from src.service.test_diagnostics.test_failure import TestFailure, TestFailuresResult

AUTO_PROJECT_TYPE = "auto"

# "at Ns.Class.Method() in C:\repo\src\File.cs:line 343" (VSTest/Roslyn)
_DOTNET_FRAME_PATTERN = re.compile(
    r"\sin\s(?P<file>[^\r\n]+?):line\s(?P<line>\d+)", re.IGNORECASE
)
# 'File "src/app.py", line 12' (CPython traceback)
_PYTHON_FRAME_PATTERN = re.compile(
    r'File\s+"(?P<file>[^"]+)",\s+line\s+(?P<line>\d+)', re.IGNORECASE
)
# "src/app.py:12: in test_x" (pytest long traceback)
_PYTEST_FRAME_PATTERN = re.compile(
    r"^(?P<file>[^\s:][^:\r\n]*\.\w+):(?P<line>\d+):", re.MULTILINE
)

_FRAME_PATTERNS = (
    _DOTNET_FRAME_PATTERN,
    _PYTHON_FRAME_PATTERN,
    _PYTEST_FRAME_PATTERN,
)


def extract_failure_location(text: str) -> tuple[str | None, int | None]:
    """Find the first source location recorded in a stack trace.

    Assertion helpers of the test framework are compiled without debug symbols,
    so they contribute no file/line frames; the first frame carrying a location
    is therefore the shallowest project frame and the most useful anchor.
    """

    for pattern in _FRAME_PATTERNS:
        for match in pattern.finditer(text or ""):
            file_value = match.group("file").strip()
            if not file_value:
                continue
            try:
                line_value = int(match.group("line"))
            except ValueError:
                continue
            return file_value, line_value
    return None, None


@dataclass(frozen=True)
class TestFailureContext:
    """Inputs available when choosing a test-result parser."""

    __test__ = False

    output: str = ""
    results_path: Path | None = None
    language: str | None = None
    project_type: str = AUTO_PROJECT_TYPE
    changed_files: tuple[str, ...] = ()


class TestFailureParser(ABC):
    """Parse the results of one test ecosystem into failures."""

    __test__ = False

    parser_name: ClassVar[str] = "generic"
    languages: ClassVar[frozenset[str]] = frozenset()
    project_types: ClassVar[frozenset[str]] = frozenset()
    result_suffixes: ClassVar[frozenset[str]] = frozenset()

    def matches(self, context: TestFailureContext) -> bool:
        results_path = context.results_path
        if (
            results_path is not None
            and results_path.suffix.lower() in self.result_suffixes
        ):
            return True
        project_type = (context.project_type or "").lower()
        if project_type and project_type in self.project_types:
            return True
        language = (context.language or "").lower()
        return bool(language) and language in self.languages

    @abstractmethod
    def parse(self, context: TestFailureContext) -> list[TestFailure]:
        """Extract failing tests from a test run."""

    def build(
        self, context: TestFailureContext, *, max_failures: int
    ) -> TestFailuresResult:
        failures = self.parse(context)
        return TestFailuresResult(
            parser=self.parser_name,
            available=bool(failures),
            failures=failures[: max(int(max_failures), 1)],
        )


class TestFailureParserResolver:
    """Select the test-result parser for a repository/runner combination."""

    __test__ = False

    def __init__(
        self,
        parsers: Sequence[TestFailureParser] | None = None,
        fallback: TestFailureParser | None = None,
    ) -> None:
        from src.service.test_diagnostics.junit_parser import JunitTestFailureParser
        from src.service.test_diagnostics.text_parser import TextTestFailureParser
        from src.service.test_diagnostics.trx_parser import TrxTestFailureParser

        self._parsers: tuple[TestFailureParser, ...] = tuple(
            parsers
            if parsers is not None
            else (TrxTestFailureParser(), JunitTestFailureParser())
        )
        self._fallback = fallback or TextTestFailureParser()

    def resolve(self, context: TestFailureContext) -> TestFailureParser:
        for parser in self._parsers:
            if parser.matches(context):
                return parser
        return self._fallback

    def parse(
        self, context: TestFailureContext, *, max_failures: int = 10
    ) -> TestFailuresResult:
        parser = self.resolve(context)
        result = parser.build(context, max_failures=max_failures)
        if result.failures or parser is self._fallback:
            return result
        # A structured artifact may be missing or truncated; the raw runner
        # output still carries the failure reason and must not be discarded.
        return self._fallback.build(context, max_failures=max_failures)
