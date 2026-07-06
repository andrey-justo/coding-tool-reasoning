from __future__ import annotations

from pathlib import Path

from src.service.localizer.ast.symbol_set import SymbolSet


class GenericSymbolExtractor:
    def extract(self, path: Path, source: str) -> SymbolSet:
        raise NotImplementedError
