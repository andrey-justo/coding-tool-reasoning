from __future__ import annotations

from pathlib import Path
from typing import Iterable

from src.service.localizer.ast.extractors import (
    PythonSymbolExtractor,
    RegexSymbolExtractor,
)
from src.service.localizer.models import LocalizationHit
from src.service.localizer.utils import extract_symbols, safe_read_text

_PYTHON_EXTENSIONS = {".py", ".pyi", ".pyw"}


class AstMatchingStrategy:
    """Language-aware symbol matching strategy.

    - Python files use native Python AST parsing.
    - Other files use generic structural symbol extraction.
    """

    name = "ast"

    def __init__(self, max_file_size_bytes: int = 500_000) -> None:
        self.max_file_size_bytes = max_file_size_bytes
        self._python_extractor = PythonSymbolExtractor()
        self._generic_extractor = RegexSymbolExtractor()

    def _extract_definitions(self, rel_path: str, source: str) -> set[str]:
        path = Path(rel_path)
        if path.suffix.lower() in _PYTHON_EXTENSIONS:
            return self._python_extractor.extract(path, source).definitions
        return self._generic_extractor.extract(path, source).definitions

    def score(
        self,
        repo_path: Path,
        issue_text: str,
        candidate_paths: Iterable[str],
    ) -> dict[str, LocalizationHit]:
        symbols = {s.lower() for s in extract_symbols(issue_text)}
        if not symbols:
            return {}

        results: dict[str, LocalizationHit] = {}

        for rel_path in candidate_paths:
            abs_path = repo_path / rel_path
            source = safe_read_text(abs_path, self.max_file_size_bytes)
            if not source:
                continue

            names = self._extract_definitions(rel_path, source)
            if not names:
                continue

            matched = sorted(symbols.intersection(names))
            if not matched:
                continue

            score = 10.0 + 4.0 * len(matched)
            results[rel_path] = LocalizationHit(
                path=rel_path,
                score=score,
                reasons=[f"ast symbol matched: {', '.join(matched[:8])}"],
            )

        return results
