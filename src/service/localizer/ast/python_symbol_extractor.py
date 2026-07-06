from __future__ import annotations

import ast
from pathlib import Path

from src.service.localizer.ast.generic_symbol_extractor import GenericSymbolExtractor
from src.service.localizer.ast.symbol_set import SymbolSet


class PythonSymbolExtractor(GenericSymbolExtractor):
    def extract(self, path: Path, source: str) -> SymbolSet:
        definitions: set[str] = set()
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return SymbolSet(definitions=definitions)

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                definitions.add(node.name.lower())

        return SymbolSet(definitions=definitions)
