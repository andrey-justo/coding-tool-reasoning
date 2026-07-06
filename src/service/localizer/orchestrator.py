from __future__ import annotations

from pathlib import Path

from src.service.localizer.discovery import discover_repository_code_files
from src.service.localizer.models import (
    LocalizationHit,
    LocalizationStrategy,
    LocalizerResult,
)
from src.service.localizer.strategies.ast_matching import AstMatchingStrategy
from src.service.localizer.strategies.filename import FilenameMatchingStrategy
from src.service.localizer.strategies.regex_content import RegexContentMatchingStrategy
from src.service.localizer.strategies.semantic_nlp import SemanticNlpMatchingStrategy
from src.service.localizer.strategies.symbol_impact import SymbolImpactStrategy


class RepositoryIssueLocalizer:
    """Locate relevant files from repository + issue text using pluggable strategies."""

    def __init__(
        self,
        strategies: list[LocalizationStrategy] | None = None,
        *,
        enable_semantic_nlp: bool = False,
    ) -> None:
        if strategies is not None:
            self.strategies = strategies
            return

        assembled: list[LocalizationStrategy] = [
            FilenameMatchingStrategy(),
            RegexContentMatchingStrategy(),
            AstMatchingStrategy(),
            SymbolImpactStrategy(),
        ]
        if enable_semantic_nlp:
            assembled.insert(2, SemanticNlpMatchingStrategy())

        self.strategies = assembled

    def localize(
        self,
        repo_path: Path,
        issue_text: str,
        top_k: int = 5,
        candidate_paths: list[str] | None = None,
    ) -> LocalizerResult:
        candidates = candidate_paths or discover_repository_code_files(repo_path)
        if not candidates:
            return LocalizerResult(selected_files=[], details=[])

        aggregate: dict[str, LocalizationHit] = {
            path: LocalizationHit(path=path, score=0.0, reasons=[])
            for path in candidates
        }

        for strategy in self.strategies:
            strategy_hits = strategy.score(repo_path, issue_text, candidates)
            for rel_path, hit in strategy_hits.items():
                current = aggregate.setdefault(
                    rel_path,
                    LocalizationHit(path=rel_path, score=0.0),
                )
                current.score += hit.score
                current.reasons.extend(
                    f"[{strategy.name}] {reason}" for reason in hit.reasons
                )

        ranked = sorted(
            aggregate.values(),
            key=lambda item: (item.score, -len(item.path)),
            reverse=True,
        )

        selected = [item.path for item in ranked if item.score > 0][: max(1, top_k)]
        if not selected:
            selected = candidates[: max(1, top_k)]

        details = [
            {
                "path": item.path,
                "score": round(item.score, 4),
                "reasons": item.reasons[:8],
            }
            for item in ranked[: max(top_k, 10)]
        ]
        return LocalizerResult(selected_files=selected, details=details)
