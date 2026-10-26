"""Fallback parsing of raw test-runner output into structured failures."""

from __future__ import annotations

import re
from typing import ClassVar

from src.service.test_diagnostics.failure_parser import (
    TestFailureContext,
    TestFailureParser,
    extract_failure_location,
)
from src.service.test_diagnostics.test_failure import TestFailure

# "FAILED tests/test_app.py::test_runs - AssertionError: boom" (pytest summary)
_PYTEST_SUMMARY_PATTERN = re.compile(
    r"^FAILED\s+(?P<test>\S+)(?:\s+-\s+(?P<message>.*))?$", re.MULTILINE
)
# "  Failed Ns.Class.Method [12 ms]" / "  Com falha Ns.Class.Method" (VSTest)
_VSTEST_SUMMARY_PATTERN = re.compile(
    r"^\s*(?:Failed|Error)\s+(?P<test>[\w.+<>`,\[\]]+)", re.MULTILINE
)
_FAILURE_KEYWORD_PATTERN = re.compile(r"\b(fail|failed|error|assert)\b", re.IGNORECASE)


class TextTestFailureParser(TestFailureParser):
    """Universal fallback used when no structured result artifact is usable."""

    parser_name: ClassVar[str] = "generic"

    def matches(self, context: TestFailureContext) -> bool:
        return True

    def parse(self, context: TestFailureContext) -> list[TestFailure]:
        output = context.output or ""
        if not output.strip():
            return []

        failures: list[TestFailure] = []
        seen: set[str] = set()

        for pattern in (_PYTEST_SUMMARY_PATTERN, _VSTEST_SUMMARY_PATTERN):
            for match in pattern.finditer(output):
                test_name = match.group("test").strip()
                if not test_name or test_name in seen:
                    continue
                seen.add(test_name)
                groups = match.groupdict()
                message = (groups.get("message") or "").strip()
                file_value, line_value = extract_failure_location(test_name)
                failures.append(
                    TestFailure(
                        test_name=test_name,
                        message=message,
                        file=file_value,
                        line=line_value,
                        raw=match.group(0).strip(),
                    )
                )

        if failures:
            return failures

        # No runner-specific summary was recognized; the failing lines of the
        # output are still better evidence than discarding the failure entirely.
        candidate_lines = [
            line.strip()
            for line in output.splitlines()
            if _FAILURE_KEYWORD_PATTERN.search(line)
        ]
        if not candidate_lines:
            return []

        joined = "\n".join(candidate_lines[-20:])
        file_value, line_value = extract_failure_location(output)
        return [
            TestFailure(
                test_name="unparsed-test-failure",
                message=candidate_lines[-1],
                stack_trace=joined,
                file=file_value,
                line=line_value,
                raw=joined,
            )
        ]
