from __future__ import annotations

from pathlib import Path
from typing import Iterable

from src.service.localizer.models import LocalizationHit
from src.service.localizer.utils import extract_tokens


class FilenameMatchingStrategy:
    name = "filename"

    def score(
        self,
        repo_path: Path,
        issue_text: str,
        candidate_paths: Iterable[str],
    ) -> dict[str, LocalizationHit]:
        tokens = extract_tokens(issue_text)
        results: dict[str, LocalizationHit] = {}

        for rel_path in candidate_paths:
            rel_lower = rel_path.lower()
            stem = Path(rel_path).stem.lower()
            score = 0.0
            matched: list[str] = []
            for token in tokens:
                if token in stem:
                    score += 8.0
                    matched.append(token)
                elif token in rel_lower:
                    score += 3.0
                    matched.append(token)
            if score > 0:
                results[rel_path] = LocalizationHit(
                    path=rel_path,
                    score=score,
                    reasons=[f"filename matched: {', '.join(sorted(set(matched)))}"],
                )

        return results
