from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

from src.service.localizer.models import LocalizationHit
from src.service.localizer.utils import extract_symbols, safe_read_text


class RegexContentMatchingStrategy:
    name = "regex"

    def __init__(self, max_file_size_bytes: int = 350_000) -> None:
        self.max_file_size_bytes = max_file_size_bytes

    def score(
        self,
        repo_path: Path,
        issue_text: str,
        candidate_paths: Iterable[str],
    ) -> dict[str, LocalizationHit]:
        symbols = extract_symbols(issue_text)
        if not symbols:
            return {}

        # Match word boundaries for extracted symbols.
        pattern = re.compile(r"\b(" + "|".join(re.escape(s) for s in symbols[:20]) + r")\b", re.IGNORECASE)
        results: dict[str, LocalizationHit] = {}

        for rel_path in candidate_paths:
            abs_path = repo_path / rel_path
            text = safe_read_text(abs_path, self.max_file_size_bytes)
            if not text:
                continue

            matches = pattern.findall(text)
            if not matches:
                continue

            freq = len(matches)
            unique = sorted({m.lower() for m in matches})
            score = min(20.0, 1.5 * freq + len(unique))
            results[rel_path] = LocalizationHit(
                path=rel_path,
                score=score,
                reasons=[f"regex content matched {len(unique)} symbols ({freq} hits)"],
            )

        return results
