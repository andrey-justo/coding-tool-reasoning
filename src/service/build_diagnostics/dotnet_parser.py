from __future__ import annotations

import re
from typing import ClassVar

from src.service.build_diagnostics.build_diagnostic import (
    ERROR_SEVERITY,
    WARNING_SEVERITY,
    BuildDiagnostic,
)
from src.service.build_diagnostics.diagnostic_parser import BuildDiagnosticParser

# MSBuild/Roslyn: "path\File.cs(292,45): error CS1503: message [path\proj.csproj]"
_POSITIONED_PATTERN = re.compile(
    r"^(?P<file>.+?)\((?P<line>\d+)(?:,(?P<column>\d+))?\)\s*:\s*"
    r"(?P<severity>error|warning)\s+(?P<code>[A-Za-z]+[0-9]+)\s*:\s*"
    r"(?P<message>.*?)\s*(?:\[(?P<project>[^\]]+)\])?$"
)

# MSBuild without a source position: "CSC : error CS5001: message [proj]"
_UNPOSITIONED_PATTERN = re.compile(
    r"^(?P<file>.*?)\s*:\s*(?P<severity>error|warning)\s+(?P<code>[A-Za-z]+[0-9]+)"
    r"\s*:\s*(?P<message>.*?)\s*(?:\[(?P<project>[^\]]+)\])?$"
)


class DotnetBuildDiagnosticParser(BuildDiagnosticParser):
    """Parse MSBuild/Roslyn diagnostics emitted by ``dotnet build``."""

    parser_name: ClassVar[str] = "dotnet"
    languages: ClassVar[frozenset[str]] = frozenset({"c#", "csharp", "dotnet", "f#"})

    def parse(self, output: str) -> list[BuildDiagnostic]:
        diagnostics: list[BuildDiagnostic] = []
        seen: set[tuple[str | None, int | None, str | None, str]] = set()

        for raw_line in output.splitlines():
            line = raw_line.strip()
            if not line:
                continue

            match = _POSITIONED_PATTERN.match(line) or _UNPOSITIONED_PATTERN.match(line)
            if match is None:
                continue

            groups = match.groupdict()
            severity = (
                ERROR_SEVERITY
                if groups.get("severity", "").lower() == "error"
                else WARNING_SEVERITY
            )
            file_name = (groups.get("file") or "").strip() or None
            message = (groups.get("message") or "").strip()
            line_number = int(groups["line"]) if groups.get("line") else None
            column = int(groups["column"]) if groups.get("column") else None
            code = groups.get("code")

            key = (file_name, line_number, code, message)
            if key in seen:
                continue
            seen.add(key)

            diagnostics.append(
                BuildDiagnostic(
                    message=message,
                    severity=severity,
                    file=file_name,
                    line=line_number,
                    column=column,
                    code=code,
                    project=(groups.get("project") or "").strip() or None,
                    raw=line,
                )
            )

        return diagnostics
