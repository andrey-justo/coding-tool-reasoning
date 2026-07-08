from __future__ import annotations

import importlib
from pathlib import Path

from src.service.localizer.ast.generic_symbol_extractor import GenericSymbolExtractor
from src.service.localizer.ast.symbol_set import SymbolSet

_LANG_MODULE_BY_SUFFIX = {
    ".js": "tree_sitter_javascript",
    ".jsx": "tree_sitter_javascript",
    ".ts": "tree_sitter_typescript",
    ".tsx": "tree_sitter_typescript",
    ".java": "tree_sitter_java",
    ".go": "tree_sitter_go",
    ".rs": "tree_sitter_rust",
    ".cs": "tree_sitter_c_sharp",
    ".cpp": "tree_sitter_cpp",
    ".cc": "tree_sitter_cpp",
    ".cxx": "tree_sitter_cpp",
    ".c": "tree_sitter_c",
    ".kt": "tree_sitter_kotlin",
}

_DECLARATION_NODE_TYPES = {
    "class_declaration",
    "interface_declaration",
    "enum_declaration",
    "struct_declaration",
    "method_declaration",
    "function_declaration",
    "function_definition",
    "type_alias_declaration",
}


class TreeSitterSymbolExtractor(GenericSymbolExtractor):
    """Extract symbols using tree-sitter language parsers when available."""

    def __init__(self) -> None:
        self._parser_cache: dict[str, object] = {}

    def _create_parser(self, suffix: str):
        module_name = _LANG_MODULE_BY_SUFFIX.get(suffix.lower())
        if not module_name:
            return None

        cached = self._parser_cache.get(module_name)
        if cached is not None:
            return cached

        try:
            ts = importlib.import_module("tree_sitter")
            language_module = importlib.import_module(module_name)

            language_obj = language_module.language()
            if hasattr(ts, "Language") and not isinstance(language_obj, ts.Language):
                language_obj = ts.Language(language_obj)

            parser = ts.Parser()
            if hasattr(parser, "set_language"):
                parser.set_language(language_obj)
            else:
                parser = ts.Parser(language_obj)

            self._parser_cache[module_name] = parser
            return parser
        except Exception:
            return None

    @staticmethod
    def _node_text(source_bytes: bytes, node) -> str:
        try:
            return source_bytes[node.start_byte : node.end_byte].decode(
                "utf-8", errors="ignore"
            )
        except Exception:
            return ""

    def extract(self, path: Path, source: str) -> SymbolSet:
        parser = self._create_parser(path.suffix)
        if parser is None:
            return SymbolSet(definitions=set())

        source_bytes = source.encode("utf-8", errors="ignore")
        try:
            tree = parser.parse(source_bytes)
        except Exception:
            return SymbolSet(definitions=set())

        definitions: set[str] = set()

        def walk(node) -> None:
            name_node = node.child_by_field_name("name") if node is not None else None
            if name_node is not None:
                symbol = self._node_text(source_bytes, name_node).strip()
                if symbol:
                    definitions.add(symbol.lower())

            if node.type in _DECLARATION_NODE_TYPES:
                for child in node.children:
                    if child.type in {"identifier", "type_identifier", "property_identifier"}:
                        symbol = self._node_text(source_bytes, child).strip()
                        if symbol:
                            definitions.add(symbol.lower())

            if node.type == "variable_declarator":
                # Covers JS/TS arrow-style declarations such as const run = () => {}
                for child in node.children:
                    if child.type in {"identifier", "property_identifier"}:
                        symbol = self._node_text(source_bytes, child).strip()
                        if symbol:
                            definitions.add(symbol.lower())

            for child in node.children:
                walk(child)

        walk(tree.root_node)
        return SymbolSet(definitions=definitions)
