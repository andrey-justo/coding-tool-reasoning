"""Build diagnostics services: strategy-based compiler output parsing."""

from src.service.build_diagnostics.build_diagnostic import (
    ERROR_SEVERITY,
    WARNING_SEVERITY,
    BuildDiagnostic,
    BuildDiagnosticsResult,
)
from src.service.build_diagnostics.diagnostic_parser import (
    BuildDiagnosticContext,
    BuildDiagnosticParser,
    BuildDiagnosticParserResolver,
    match_diagnostic_file,
)
from src.service.build_diagnostics.dotnet_parser import DotnetBuildDiagnosticParser
from src.service.build_diagnostics.generic_parser import GenericBuildDiagnosticParser
from src.service.build_diagnostics.python_parser import PythonBuildDiagnosticParser

__all__ = [
    "ERROR_SEVERITY",
    "WARNING_SEVERITY",
    "BuildDiagnostic",
    "BuildDiagnosticContext",
    "BuildDiagnosticParser",
    "BuildDiagnosticParserResolver",
    "BuildDiagnosticsResult",
    "DotnetBuildDiagnosticParser",
    "GenericBuildDiagnosticParser",
    "PythonBuildDiagnosticParser",
    "match_diagnostic_file",
]
