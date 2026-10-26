"""Test diagnostics services: strategy-based test result parsing."""

from src.service.test_diagnostics.failure_parser import (
    TestFailureContext,
    TestFailureParser,
    TestFailureParserResolver,
    extract_failure_location,
)
from src.service.test_diagnostics.junit_parser import JunitTestFailureParser
from src.service.test_diagnostics.test_failure import TestFailure, TestFailuresResult
from src.service.test_diagnostics.text_parser import TextTestFailureParser
from src.service.test_diagnostics.trx_parser import TrxTestFailureParser

__all__ = [
    "JunitTestFailureParser",
    "TestFailure",
    "TestFailureContext",
    "TestFailureParser",
    "TestFailureParserResolver",
    "TestFailuresResult",
    "TextTestFailureParser",
    "TrxTestFailureParser",
    "extract_failure_location",
]
