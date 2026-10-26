from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

ERROR_SEVERITY = "error"
WARNING_SEVERITY = "warning"


@dataclass(frozen=True)
class BuildDiagnostic:
    """One compiler/build message normalized across ecosystems."""

    message: str
    severity: str = ERROR_SEVERITY
    file: str | None = None
    line: int | None = None
    column: int | None = None
    code: str | None = None
    project: str | None = None
    raw: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class BuildDiagnosticsResult:
    """Diagnostics extracted from a build log by one parser."""

    parser: str
    available: bool = True
    diagnostics: list[BuildDiagnostic] = field(default_factory=list)

    @property
    def errors(self) -> list[BuildDiagnostic]:
        return [
            diagnostic
            for diagnostic in self.diagnostics
            if diagnostic.severity == ERROR_SEVERITY
        ]

    def to_dict(self) -> dict[str, Any]:
        return {
            "parser": self.parser,
            "available": self.available,
            "diagnostics": [diagnostic.to_dict() for diagnostic in self.diagnostics],
        }
