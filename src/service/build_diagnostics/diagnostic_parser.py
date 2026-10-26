"""Strategy-based parsing of build output into structured diagnostics.

Parsers are selected from the repository verification project type plus the
language inferred from the changed files, mirroring how build/test commands are
discovered, so compiler output handling is not hardcoded into the repair tool.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar, Iterable

from src.service.build_diagnostics.build_diagnostic import (
    ERROR_SEVERITY,
    BuildDiagnostic,
    BuildDiagnosticsResult,
)

AUTO_PROJECT_TYPE = "auto"


@dataclass(frozen=True)
class BuildDiagnosticContext:
    """Inputs available when choosing a build-output parser."""

    language: str | None = None
    project_type: str = AUTO_PROJECT_TYPE
    changed_files: tuple[str, ...] = ()


class BuildDiagnosticParser(ABC):
    """Parse the output of one build ecosystem into diagnostics."""

    parser_name: ClassVar[str] = "generic"
    languages: ClassVar[frozenset[str]] = frozenset()

    def matches(self, context: BuildDiagnosticContext) -> bool:
        if context.project_type and context.project_type.lower() == self.parser_name:
            return True
        language = (context.language or "").lower()
        return bool(language) and language in self.languages

    @abstractmethod
    def parse(self, output: str) -> list[BuildDiagnostic]:
        """Extract diagnostics from raw build output."""

    def build(self, output: str, *, max_diagnostics: int) -> BuildDiagnosticsResult:
        diagnostics = self.parse(output or "")
        errors = [
            diagnostic
            for diagnostic in diagnostics
            if diagnostic.severity == ERROR_SEVERITY
        ]
        # Errors are what block the build, so warnings never crowd them out of
        # the bounded diagnostic window sent to the repair model.
        selected = errors or diagnostics
        return BuildDiagnosticsResult(
            parser=self.parser_name,
            available=bool(selected),
            diagnostics=selected[: max(int(max_diagnostics), 1)],
        )


def match_diagnostic_file(
    diagnostic_file: str | None, known_files: Iterable[str]
) -> str | None:
    """Map a build-reported path to one of the known repository-relative files.

    Build commands run inside a temporary worktree, so diagnostics carry absolute
    paths that never equal the repository-relative keys used by the pipeline.
    Matching is therefore done on normalized path suffixes.
    """

    if not diagnostic_file:
        return None

    normalized = diagnostic_file.replace("\\", "/").strip().rstrip(":")
    if not normalized:
        return None

    candidates = list(known_files)
    best_match: str | None = None
    best_length = -1
    for candidate in candidates:
        candidate_normalized = candidate.replace("\\", "/").strip()
        if not candidate_normalized:
            continue
        if normalized == candidate_normalized or normalized.endswith(
            "/" + candidate_normalized
        ):
            if len(candidate_normalized) > best_length:
                best_match = candidate
                best_length = len(candidate_normalized)

    if best_match is not None:
        return best_match

    diagnostic_name = Path(normalized).name.lower()
    for candidate in candidates:
        if Path(candidate.replace("\\", "/")).name.lower() == diagnostic_name:
            return candidate
    return None
