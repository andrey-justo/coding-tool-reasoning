from __future__ import annotations

import math
from pathlib import Path
from typing import Iterable

from src.service.localizer.models import LocalizationHit
from src.service.localizer.utils import count_token_frequency, safe_read_text


class SemanticNlpMatchingStrategy:
    """Local NLP strategy using TF-IDF cosine similarity for semantic reranking."""

    name = "semantic_nlp"

    def __init__(self, max_file_size_bytes: int = 350_000) -> None:
        self.max_file_size_bytes = max_file_size_bytes

    @staticmethod
    def _idf(num_docs: int, doc_freq: int) -> float:
        return math.log((1 + num_docs) / (1 + doc_freq)) + 1.0

    @staticmethod
    def _cosine(left: dict[str, float], right: dict[str, float]) -> float:
        if not left or not right:
            return 0.0

        dot = 0.0
        for token, value in left.items():
            dot += value * right.get(token, 0.0)

        left_norm = math.sqrt(sum(value * value for value in left.values()))
        right_norm = math.sqrt(sum(value * value for value in right.values()))
        if left_norm == 0.0 or right_norm == 0.0:
            return 0.0
        return dot / (left_norm * right_norm)

    def score(
        self,
        repo_path: Path,
        issue_text: str,
        candidate_paths: Iterable[str],
    ) -> dict[str, LocalizationHit]:
        issue_tf = count_token_frequency(issue_text)
        if not issue_tf:
            return {}

        docs_tf: dict[str, dict[str, int]] = {}
        doc_freq: dict[str, int] = {}

        for rel_path in candidate_paths:
            text = safe_read_text(repo_path / rel_path, self.max_file_size_bytes)
            if not text:
                continue

            tf = count_token_frequency(text)
            if not tf:
                continue

            docs_tf[rel_path] = tf
            for token in tf.keys():
                doc_freq[token] = doc_freq.get(token, 0) + 1

        if not docs_tf:
            return {}

        num_docs = len(docs_tf)

        issue_vector: dict[str, float] = {}
        for token, freq in issue_tf.items():
            issue_vector[token] = float(freq) * self._idf(num_docs, doc_freq.get(token, 0))

        results: dict[str, LocalizationHit] = {}
        for rel_path, tf in docs_tf.items():
            doc_vector: dict[str, float] = {}
            for token, freq in tf.items():
                doc_vector[token] = float(freq) * self._idf(num_docs, doc_freq.get(token, 0))

            cosine = self._cosine(issue_vector, doc_vector)
            if cosine <= 0.0:
                continue

            score = min(25.0, cosine * 40.0)
            results[rel_path] = LocalizationHit(
                path=rel_path,
                score=score,
                reasons=[f"semantic tf-idf cosine={cosine:.4f}"],
            )

        return results
