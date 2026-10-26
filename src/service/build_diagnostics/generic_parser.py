from __future__ import annotations

import re
from typing import ClassVar

from src.service.build_diagnostics.build_diagnostic import (
    ERROR_SEVERITY,
    BuildDiagnostic,
)
from src.service.build_diagnostics.diagnostic_parser import BuildDiagnosticParser

# gcc/clang/tsc style: 'src/foo.c:12:5: error: expected ;'
_POSITIONED_PATTERN = re.compile(
    r"^(?P<file>[^\s:][^:]*):(?P<line>\d+)(?::(?P<column>\d+))?:\s*"
    r"(?:(?P<severity>error|fatal error)\s*:\s*)?(?P<message>.*)$",
    re.IGNORECASE,
)

_ERROR_TOKEN_PATTERN = re.compile(r"\b(error|failed|fatal)\b", re.IGNORECASE)


class GenericBuildDiagnosticParser(BuildDiagnosticParser):
    """Fallback parser for ecosystems without a dedicated strategy."""

    parser_name: ClassVar[str] = "generic"
    languages: ClassVar[frozenset[str]] = frozenset()

    def matches(self, context) -> bool:  # noqa: ANN001 - resolver passes context
        return True

    def parse(self, output: str) -> list[BuildDiagnostic]:
        diagnostics: list[BuildDiagnostic] = []

        for raw_line in output.splitlines():
            line = raw_line.strip()
            if not line or not _ERROR_TOKEN_PATTERN.search(line):
                continue

            match = _POSITIONED_PATTERN.match(line)
            if match is not None and match.group("severity"):
                diagnostics.append(
                    BuildDiagnostic(
                        message=match.group("message").strip(),
                        severity=ERROR_SEVERITY,
                        file=match.group("file"),
                        line=int(match.group("line")),
                        column=int(match.group("column"))
                        if match.group("column")
                        else None,
                        raw=line,
                    )
                )
                continue

            diagnostics.append(
                BuildDiagnostic(message=line, severity=ERROR_SEVERITY, raw=line)
            )

        return diagnostics
