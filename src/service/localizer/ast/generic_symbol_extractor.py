from __future__ import annotations

from pathlib import Path

from src.models.localizer.models import SymbolSet


class GenericSymbolExtractor:
    def extract(self, path: Path, source: str) -> SymbolSet:
        raise NotImplementedError
