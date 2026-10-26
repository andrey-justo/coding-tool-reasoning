"""Resolve test parsers independently of their shared base class."""

from __future__ import annotations

from typing import Sequence

from src.service.test_diagnostics.failure_parser import (
    TestFailureContext,
    TestFailureParser,
)
from src.service.test_diagnostics.junit_parser import JunitTestFailureParser
from src.service.test_diagnostics.test_failure import TestFailuresResult
from src.service.test_diagnostics.text_parser import TextTestFailureParser
from src.service.test_diagnostics.trx_parser import TrxTestFailureParser


class TestFailureParserResolver:
    """Select the test-result parser for a repository/runner combination."""

    __test__ = False

    def __init__(
        self,
        parsers: Sequence[TestFailureParser] | None = None,
        fallback: TestFailureParser | None = None,
    ) -> None:
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
        # Missing or truncated artifacts must not hide the raw runner failure.
        return self._fallback.build(context, max_failures=max_failures)
