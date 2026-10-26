from __future__ import annotations

from pathlib import Path

from src.models.localizer.models import (
    LocalizationHit,
    LocalizationStrategy,
    LocalizerResult,
)
from src.service.localizer.discovery import discover_repository_code_files
from src.service.localizer.strategies.ast_matching import AstMatchingStrategy
from src.service.localizer.strategies.filename import FilenameMatchingStrategy
from src.service.localizer.strategies.graph_memory import (
    GraphMemoryRelationshipStrategy,
)
from src.service.localizer.strategies.regex_content import RegexContentMatchingStrategy
from src.service.localizer.strategies.semantic_nlp import SemanticNlpMatchingStrategy
from src.service.localizer.strategies.symbol_impact import SymbolImpactStrategy
from src.service.localizer.strategies.tfidf_content import TfIdfContentStrategy


class RepositoryIssueLocalizer:
    """Locate relevant files from repository + issue text using pluggable strategies."""

    DEFAULT_MIN_RELATIVE_SCORE = 0.5

    #: Relative influence of each strategy on the aggregated ranking. Strategies
    #: produce scores on incompatible scales, so summing raw values lets the
    #: most verbose strategy decide the outcome regardless of its precision.
    #: Each strategy is therefore rescaled to ``[0, weight]`` before summing.
    DEFAULT_STRATEGY_WEIGHTS = {
        "filename": 1.5,
        "regex": 0.5,
        "tfidf": 3.0,
        "graph_memory": 1.0,
        "semantic_nlp": 1.0,
        "ast": 1.0,
        "symbol_impact": 1.0,
    }

    def __init__(
        self,
        strategies: list[LocalizationStrategy] | None = None,
        *,
        enable_semantic_nlp: bool = False,
        enable_graph_memory: bool = True,
        graph_memory_hops: int = 2,
        semantic_index_dir: str = ".semantic_index",
        persist_semantic_index: bool = True,
        vector_backend: str = "local_tfidf",
        graph_storage_backend: str = "in_memory",
        enable_neo4j_beta: bool = False,
        neo4j_uri: str | None = None,
        neo4j_username: str | None = None,
        neo4j_password: str | None = None,
        neo4j_password_env_var: str = "NEO4J_PASSWORD",
        neo4j_database: str = "neo4j",
        strategy_weights: dict[str, float] | None = None,
        min_relative_score: float = DEFAULT_MIN_RELATIVE_SCORE,
    ) -> None:
        if not 0 < min_relative_score <= 1:
            raise ValueError("min_relative_score must be greater than 0 and at most 1.")
        self.min_relative_score = min_relative_score
        self.strategy_weights = dict(
            strategy_weights
            if strategy_weights is not None
            else self.DEFAULT_STRATEGY_WEIGHTS
        )
        if strategies is not None:
            self.strategies = strategies
            return

        assembled: list[LocalizationStrategy] = [
            FilenameMatchingStrategy(),
            RegexContentMatchingStrategy(),
            TfIdfContentStrategy(),
            GraphMemoryRelationshipStrategy(
                hops=graph_memory_hops,
                semantic_index_dir=semantic_index_dir,
                persist_semantic_index=persist_semantic_index,
                vector_backend=vector_backend,
                graph_storage_backend=graph_storage_backend,
                enable_neo4j_beta=enable_neo4j_beta,
                neo4j_uri=neo4j_uri,
                neo4j_username=neo4j_username,
                neo4j_password=neo4j_password,
                neo4j_password_env_var=neo4j_password_env_var,
                neo4j_database=neo4j_database,
            )
            if enable_graph_memory
            else None,
            AstMatchingStrategy(),
            SymbolImpactStrategy(),
        ]
        assembled = [strategy for strategy in assembled if strategy is not None]
        if enable_semantic_nlp:
            assembled.insert(2, SemanticNlpMatchingStrategy())

        self.strategies = assembled

    def localize(
        self,
        repo_path: Path,
        issue_text: str,
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
            if not strategy_hits:
                continue

            # Rescale this strategy's output to [0, weight] so that strategies
            # with naturally larger raw scores do not dominate the ensemble.
            weight = self.strategy_weights.get(strategy.name, 1.0)
            best = max(hit.score for hit in strategy_hits.values())
            normalizer = (weight / best) if best > 0 else 0.0

            for rel_path, hit in strategy_hits.items():
                current = aggregate.setdefault(
                    rel_path,
                    LocalizationHit(path=rel_path, score=0.0),
                )
                current.score += hit.score * normalizer
                current.reasons.extend(
                    f"[{strategy.name}] {reason}" for reason in hit.reasons
                )

        ranked = sorted(
            aggregate.values(),
            key=lambda item: (item.score, -len(item.path)),
            reverse=True,
        )

        best_score = ranked[0].score if ranked else 0.0
        threshold = best_score * self.min_relative_score
        selected = [
            item.path
            for item in ranked
            if item.score > 0 and item.score >= threshold
        ]

        details = [
            {
                "path": item.path,
                "score": round(item.score, 4),
                "relative_score": (
                    round(item.score / best_score, 4) if best_score > 0 else 0.0
                ),
                "selected": item.path in selected,
                "reasons": item.reasons[:8],
            }
            for item in ranked
        ]
        return LocalizerResult(selected_files=selected, details=details)
