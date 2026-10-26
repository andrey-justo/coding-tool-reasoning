"""Resolve build parsers without coupling their base class to implementations."""

from __future__ import annotations

from typing import Sequence

from src.service.build_diagnostics.build_diagnostic import BuildDiagnosticsResult
from src.service.build_diagnostics.diagnostic_parser import (
    BuildDiagnosticContext,
    BuildDiagnosticParser,
)
from src.service.build_diagnostics.dotnet_parser import DotnetBuildDiagnosticParser
from src.service.build_diagnostics.generic_parser import GenericBuildDiagnosticParser
from src.service.build_diagnostics.python_parser import PythonBuildDiagnosticParser


class BuildDiagnosticParserResolver:
    """Select the build-output parser for a repository/language combination."""

    def __init__(
        self,
        parsers: Sequence[BuildDiagnosticParser] | None = None,
        fallback: BuildDiagnosticParser | None = None,
    ) -> None:
        self._parsers: tuple[BuildDiagnosticParser, ...] = tuple(
            parsers
            if parsers is not None
            else (DotnetBuildDiagnosticParser(), PythonBuildDiagnosticParser())
        )
        self._fallback = fallback or GenericBuildDiagnosticParser()

    def resolve(self, context: BuildDiagnosticContext) -> BuildDiagnosticParser:
        for parser in self._parsers:
            if parser.matches(context):
                return parser
        return self._fallback

    def parse(
        self,
        output: str,
        context: BuildDiagnosticContext,
        *,
        max_diagnostics: int = 20,
    ) -> BuildDiagnosticsResult:
        parser = self.resolve(context)
        result = parser.build(output, max_diagnostics=max_diagnostics)
        if result.diagnostics or parser is self._fallback:
            return result
        # Unrecognized language output must still expose the failure cause.
        return self._fallback.build(output, max_diagnostics=max_diagnostics)
