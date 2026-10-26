from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Iterable

from src.models.localizer.models import LocalizationHit
from src.service.localizer.utils import extract_weighted_symbols, safe_read_text


class TfIdfContentStrategy:
    """Score files by corpus-aware rarity of the symbols mentioned in the issue.

    Absolute match counts reward large files regardless of relevance, which makes
    whole-repository localization degenerate into a file-size ranking. This
    strategy corrects that in three ways:

    * symbols occurring in more than ``max_document_frequency_ratio`` of the
      corpus are discarded, because they cannot discriminate between files;
    * each surviving symbol contributes proportionally to its inverse document
      frequency, so rare identifiers dominate common ones;
    * repeated occurrences saturate logarithmically, so a single long file
      cannot outrank a precise match by sheer volume.
    """

    name = "tfidf"

    def __init__(
        self,
        max_file_size_bytes: int = 350_000,
        max_symbols: int = 40,
        max_document_frequency_ratio: float = 0.10,
        max_score: float = 30.0,
    ) -> None:
        self.max_file_size_bytes = max_file_size_bytes
        self.max_symbols = max_symbols
        self.max_document_frequency_ratio = max_document_frequency_ratio
        self.max_score = max_score

    def score(
        self,
        repo_path: Path,
        issue_text: str,
        candidate_paths: Iterable[str],
    ) -> dict[str, LocalizationHit]:
        weighted_symbols = extract_weighted_symbols(issue_text)[: self.max_symbols]
        if not weighted_symbols:
            return {}

        patterns = {
            symbol: re.compile(r"\b" + re.escape(symbol) + r"\b", re.IGNORECASE)
            for symbol, _ in weighted_symbols
        }

        term_frequency: dict[str, dict[str, int]] = {}
        document_frequency: dict[str, int] = {symbol: 0 for symbol in patterns}
        document_count = 0

        for rel_path in candidate_paths:
            text = safe_read_text(repo_path / rel_path, self.max_file_size_bytes)
            if not text:
                continue

            document_count += 1
            counts: dict[str, int] = {}
            for symbol, pattern in patterns.items():
                hits = len(pattern.findall(text))
                if hits:
                    counts[symbol] = hits
                    document_frequency[symbol] += 1
            if counts:
                term_frequency[rel_path] = counts

        if not document_count:
            return {}

        frequency_ceiling = max(
            1, int(document_count * self.max_document_frequency_ratio)
        )
        weights = {
            symbol: weight
            for symbol, weight in weighted_symbols
            if 0 < document_frequency[symbol] <= frequency_ceiling
        }
        if not weights:
            return {}

        results: dict[str, LocalizationHit] = {}
        raw_scores: dict[str, tuple[float, list[tuple[str, float]]]] = {}
        for rel_path, counts in term_frequency.items():
            score = 0.0
            matched: list[tuple[str, float]] = []
            for symbol, weight in weights.items():
                hits = counts.get(symbol, 0)
                if not hits:
                    continue
                inverse_document_frequency = math.log(
                    document_count / document_frequency[symbol]
                )
                saturation = min(3.0, 1.0 + math.log(hits))
                contribution = weight * inverse_document_frequency * saturation
                score += contribution
                matched.append((symbol, contribution))

            if score > 0:
                raw_scores[rel_path] = (score, matched)

        if not raw_scores:
            return {}

        # Rescale to a bounded range so this strategy cannot overwhelm the
        # others, while preserving the relative ordering it computed.
        best = max(score for score, _ in raw_scores.values())
        for rel_path, (score, matched) in raw_scores.items():
            matched.sort(key=lambda item: -item[1])
            top_symbols = ", ".join(symbol for symbol, _ in matched[:8])
            results[rel_path] = LocalizationHit(
                path=rel_path,
                score=self.max_score * score / best,
                reasons=[f"rare issue symbols: {top_symbols}"],
            )

        return results
