from __future__ import annotations

import re
from pathlib import Path

from src.service.localizer.ast.generic_symbol_extractor import GenericSymbolExtractor
from src.service.localizer.ast.symbol_set import SymbolSet


class RegexSymbolExtractor(GenericSymbolExtractor):
    """Language-agnostic structural symbol extractor.

    This is intentionally heuristic-based so it can cover multiple languages
    without requiring per-language parser dependencies.
    """

    _patterns = [
        re.compile(r"\bclass\s+([A-Za-z_][A-Za-z0-9_]*)"),
        re.compile(r"\binterface\s+([A-Za-z_][A-Za-z0-9_]*)"),
        re.compile(r"\benum\s+([A-Za-z_][A-Za-z0-9_]*)"),
        re.compile(r"\bstruct\s+([A-Za-z_][A-Za-z0-9_]*)"),
        re.compile(
            r"\b(?:public|private|protected|internal|static|final|virtual|override|async|inline|const|export\s+)?"
            r"(?:[A-Za-z_][A-Za-z0-9_<>,\[\]\*&\s]+)?\s+"
            r"([A-Za-z_][A-Za-z0-9_]*)\s*\([^;\n\{\)]*\)\s*(?:\{|=>)",
            re.MULTILINE,
        ),
        re.compile(r"\bfunction\s+([A-Za-z_][A-Za-z0-9_]*)\s*\("),
        re.compile(r"\bdef\s+([A-Za-z_][A-Za-z0-9_]*)\s*\("),
    ]

    def extract(self, path: Path, source: str) -> SymbolSet:
        definitions: set[str] = set()
        for pattern in self._patterns:
            for token in pattern.findall(source):
                if token:
                    definitions.add(token.lower())
        return SymbolSet(definitions=definitions)
