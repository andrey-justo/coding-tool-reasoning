"""Parse JUnit XML result files into structured test failures."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import ClassVar

from src.service.test_diagnostics.failure_parser import (
    TestFailureContext,
    TestFailureParser,
    extract_failure_location,
)
from src.service.test_diagnostics.test_failure import TestFailure


class JunitTestFailureParser(TestFailureParser):
    """Extract failing test cases from a JUnit XML document."""

    parser_name: ClassVar[str] = "junit"
    languages: ClassVar[frozenset[str]] = frozenset(
        {"python", "java", "javascript", "typescript"}
    )
    project_types: ClassVar[frozenset[str]] = frozenset(
        {"python", "java", "maven", "gradle", "node", "npm"}
    )
    result_suffixes: ClassVar[frozenset[str]] = frozenset({".xml"})

    def parse(self, context: TestFailureContext) -> list[TestFailure]:
        results_path = context.results_path
        if results_path is None or not results_path.exists():
            return []

        try:
            root = ET.parse(results_path).getroot()
        except ET.ParseError:
            return []

        failures: list[TestFailure] = []
        for testcase in root.iter("testcase"):
            for child in testcase:
                if child.tag not in {"failure", "error"}:
                    continue

                message = str(child.attrib.get("message", "")).strip()
                detail = (child.text or "").strip()
                file_value, line_value = extract_failure_location(detail or message)
                if file_value is None:
                    file_value = testcase.attrib.get("file")
                if line_value is None and testcase.attrib.get("line"):
                    try:
                        line_value = int(testcase.attrib["line"])
                    except ValueError:
                        line_value = None

                detail_first_line = detail.splitlines()[0] if detail else ""
                failures.append(
                    TestFailure(
                        test_name=str(testcase.attrib.get("name", "")).strip()
                        or "unknown-test",
                        message=message or detail_first_line,
                        class_name=testcase.attrib.get("classname") or None,
                        stack_trace=detail,
                        file=file_value,
                        line=line_value,
                        outcome="failed" if child.tag == "failure" else "error",
                        raw=f"{message}\n{detail}".strip(),
                    )
                )

        return failures
