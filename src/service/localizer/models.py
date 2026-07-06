from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Protocol


@dataclass
class LocalizationHit:
    path: str
    score: float
    reasons: list[str] = field(default_factory=list)


@dataclass
class LocalizerResult:
    selected_files: list[str]
    details: list[dict[str, object]]


class LocalizationStrategy(Protocol):
    name: str

    def score(
        self,
        repo_path: Path,
        issue_text: str,
        candidate_paths: Iterable[str],
    ) -> dict[str, LocalizationHit]:
        ...
