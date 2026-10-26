from __future__ import annotations

import re
from typing import ClassVar

from src.service.build_diagnostics.build_diagnostic import (
    ERROR_SEVERITY,
    WARNING_SEVERITY,
    BuildDiagnostic,
)
from src.service.build_diagnostics.diagnostic_parser import BuildDiagnosticParser

# Traceback frame: '  File "src/foo.py", line 12'
_TRACEBACK_PATTERN = re.compile(
    r'^\s*File "(?P<file>[^"]+)", line (?P<line>\d+)(?:, in (?P<scope>.+))?$'
)

# Exception line closing a traceback: 'SyntaxError: invalid syntax'
_EXCEPTION_PATTERN = re.compile(
    r"^(?P<code>[A-Za-z_][A-Za-z0-9_.]*(?:Error|Exception|Warning))\s*:\s*"
    r"(?P<message>.*)$"
)

# Linter/type-checker style: 'src/foo.py:12:5: F821 undefined name'
_LINTER_PATTERN = re.compile(
    r"^(?P<file>[^\s:][^:]*\.pyi?):(?P<line>\d+)(?::(?P<column>\d+))?:\s*"
    r"(?:(?P<severity>error|warning|note)\s*:\s*)?"
    r"(?P<message>.*)$"
)

_LINTER_CODE_PATTERN = re.compile(r"^(?P<code>[A-Z]+[0-9]+)\s+(?P<message>.*)$")


class PythonBuildDiagnosticParser(BuildDiagnosticParser):
    """Parse Python compile/import/lint failures from build output."""

    parser_name: ClassVar[str] = "python"
    languages: ClassVar[frozenset[str]] = frozenset({"python", "py"})

    def parse(self, output: str) -> list[BuildDiagnostic]:
        diagnostics: list[BuildDiagnostic] = []
        pending_file: str | None = None
        pending_line: int | None = None

        for raw_line in output.splitlines():
            line = raw_line.rstrip()
            if not line.strip():
                continue

            traceback_match = _TRACEBACK_PATTERN.match(line)
            if traceback_match is not None:
                pending_file = traceback_match.group("file")
                pending_line = int(traceback_match.group("line"))
                continue

            exception_match = _EXCEPTION_PATTERN.match(line.strip())
            if exception_match is not None:
                diagnostics.append(
                    BuildDiagnostic(
                        message=exception_match.group("message").strip(),
                        severity=ERROR_SEVERITY,
                        file=pending_file,
                        line=pending_line,
                        code=exception_match.group("code"),
                        raw=line.strip(),
                    )
                )
                pending_file = None
                pending_line = None
                continue

            linter_match = _LINTER_PATTERN.match(line.strip())
            if linter_match is None:
                continue

            message = linter_match.group("message").strip()
            code: str | None = None
            code_match = _LINTER_CODE_PATTERN.match(message)
            if code_match is not None:
                code = code_match.group("code")
                message = code_match.group("message").strip()

            severity_token = (linter_match.group("severity") or "").lower()
            severity = (
                WARNING_SEVERITY
                if severity_token in {"warning", "note"}
                else ERROR_SEVERITY
            )

            diagnostics.append(
                BuildDiagnostic(
                    message=message,
                    severity=severity,
                    file=linter_match.group("file"),
                    line=int(linter_match.group("line")),
                    column=int(linter_match.group("column"))
                    if linter_match.group("column")
                    else None,
                    code=code,
                    raw=line.strip(),
                )
            )

        return diagnostics
