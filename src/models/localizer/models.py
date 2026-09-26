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
    ) -> dict[str, LocalizationHit]: ...


@dataclass
class SymbolSet:
    definitions: set[str]


@dataclass
class GraphIndex:
    docs_tf: dict[str, dict[str, int]]
    doc_freq: dict[str, int]
    definitions_by_file: dict[str, set[str]]
    references_by_file: dict[str, set[str]]
    neighbors: dict[str, set[str]]
    ast_links_by_file: dict[str, list[tuple[str, str, str]]]


@dataclass
class IndexedDocument:
    mtime_ns: int
    size: int
    tf: dict[str, int]
    definitions: set[str]
    references: set[str]
    imports: set[str]
    ast_links: list[tuple[str, str, str]]
