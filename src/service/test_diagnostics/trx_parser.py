"""Parse VSTest TRX result files into structured test failures."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import ClassVar

from src.service.test_diagnostics.failure_parser import (
    TestFailureContext,
    TestFailureParser,
    extract_failure_location,
)
from src.service.test_diagnostics.test_failure import TestFailure

_FAILED_OUTCOMES = {"failed", "error", "aborted", "timeout"}


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _find_child(element, name: str):
    for child in element:
        if _local_name(child.tag) == name:
            return child
    return None


class TrxTestFailureParser(TestFailureParser):
    """Extract failing unit tests from a VSTest TRX document."""

    parser_name: ClassVar[str] = "trx"
    languages: ClassVar[frozenset[str]] = frozenset({"c#", "csharp", "dotnet"})
    project_types: ClassVar[frozenset[str]] = frozenset({"dotnet", "csharp", "c#"})
    result_suffixes: ClassVar[frozenset[str]] = frozenset({".trx"})

    def parse(self, context: TestFailureContext) -> list[TestFailure]:
        results_path = context.results_path
        if results_path is None or not results_path.exists():
            return []

        try:
            root = ET.parse(results_path).getroot()
        except ET.ParseError:
            return []

        failures: list[TestFailure] = []
        for element in root.iter():
            if _local_name(element.tag) != "UnitTestResult":
                continue
            outcome = str(element.attrib.get("outcome", "")).lower()
            if outcome not in _FAILED_OUTCOMES:
                continue

            output = _find_child(element, "Output")
            error_info = (
                _find_child(output, "ErrorInfo") if output is not None else None
            )
            message_node = (
                _find_child(error_info, "Message") if error_info is not None else None
            )
            stack_node = (
                _find_child(error_info, "StackTrace")
                if error_info is not None
                else None
            )

            message = (
                (message_node.text or "").strip() if message_node is not None else ""
            )
            stack_trace = (
                (stack_node.text or "").strip() if stack_node is not None else ""
            )
            file_value, line_value = extract_failure_location(stack_trace or message)

            test_name = str(element.attrib.get("testName", "")).strip()
            class_name = None
            if "." in test_name:
                class_name, _, _ = test_name.rpartition(".")

            failures.append(
                TestFailure(
                    test_name=test_name or "unknown-test",
                    message=message,
                    class_name=class_name or None,
                    stack_trace=stack_trace,
                    file=file_value,
                    line=line_value,
                    outcome=outcome,
                    raw=f"{message}\n{stack_trace}".strip(),
                )
            )

        return failures
