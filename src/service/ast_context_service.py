"""AST context extraction around build-error locations.

Compiler diagnostics point at a line, but a repair model also needs the
enclosing declaration to change the right symbol. This service reuses the
tree-sitter parsers already used by the localizer and the syntax validator.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable

from src.service.localizer.ast.tree_sitter_symbol_extractor import (
    TreeSitterSymbolExtractor,
)
from src.service.syntax_validator import SyntaxValidator

_SCOPE_NODE_TYPES = {
    "class_declaration",
    "class_definition",
    "interface_declaration",
    "enum_declaration",
    "struct_declaration",
    "record_declaration",
    "record_struct_declaration",
    "namespace_declaration",
    "method_declaration",
    "constructor_declaration",
    "destructor_declaration",
    "operator_declaration",
    "property_declaration",
    "indexer_declaration",
    "event_declaration",
    "field_declaration",
    "local_function_statement",
    "function_declaration",
    "function_definition",
    "function_item",
    "method_definition",
    "type_alias_declaration",
    "decorated_definition",
}

_NAME_NODE_TYPES = {
    "identifier",
    "type_identifier",
    "property_identifier",
    "field_identifier",
    "qualified_name",
}


def declaration_signature_at(lines: list[str], start_line: int) -> str:
    """Return the declaration line, skipping attributes and decorators.

    Tree-sitter anchors an annotated declaration at its first attribute, so
    reading the start line verbatim would surface ``[Attribute(...)]`` instead
    of the signature the model needs.
    """

    index = max(0, start_line - 1)
    for offset in range(index, min(len(lines), index + 10)):
        candidate = lines[offset].strip()
        if not candidate or candidate.startswith(("[", "@", "//", "#", "/*", "*")):
            continue
        return candidate
    return ""


@dataclass(frozen=True)
class AstScope:
    """One enclosing declaration around a diagnostic line."""

    node_type: str
    name: str | None
    start_line: int
    end_line: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AstLocationContext:
    """AST neighborhood of a single diagnostic location."""

    file: str
    line: int
    available: bool
    scopes: list[AstScope] = field(default_factory=list)
    snippet: str = ""
    snippet_start_line: int = 0
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "file": self.file,
            "line": self.line,
            "available": self.available,
            "scopes": [scope.to_dict() for scope in self.scopes],
            "snippet": self.snippet,
            "snippet_start_line": self.snippet_start_line,
            "error": self.error,
        }


@dataclass
class AstOutline:
    """Top-level declarations of a file, used as cross-file context."""

    file: str
    available: bool
    declarations: list[AstScope] = field(default_factory=list)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "file": self.file,
            "available": self.available,
            "declarations": [
                declaration.to_dict() for declaration in self.declarations
            ],
            "error": self.error,
        }


class AstContextService:
    """Describe the syntactic scope and source neighborhood of error lines."""

    def __init__(self, extractor: TreeSitterSymbolExtractor | None = None) -> None:
        self._extractor = extractor or TreeSitterSymbolExtractor()

    def describe_locations(
        self,
        target_file: str,
        source: str,
        lines: Iterable[int],
        *,
        context_lines: int = 12,
        max_locations: int = 10,
    ) -> list[AstLocationContext]:
        unique_lines = sorted({int(line) for line in lines if int(line) > 0})[
            : max(int(max_locations), 1)
        ]
        if not unique_lines:
            return []

        normalized = SyntaxValidator.normalize_transport_bom(source)
        source_lines = normalized.splitlines()
        parser = self._extractor._create_parser(Path(target_file).suffix.lower())

        if parser is None:
            return [
                AstLocationContext(
                    file=target_file,
                    line=line,
                    available=False,
                    snippet=self._snippet(source_lines, line, context_lines),
                    snippet_start_line=self._snippet_start(line, context_lines),
                    error="No tree-sitter parser available for this file type.",
                )
                for line in unique_lines
            ]

        try:
            tree = parser.parse(normalized.encode("utf-8", errors="ignore"))
        except Exception as exc:
            return [
                AstLocationContext(
                    file=target_file,
                    line=line,
                    available=False,
                    snippet=self._snippet(source_lines, line, context_lines),
                    snippet_start_line=self._snippet_start(line, context_lines),
                    error=f"{type(exc).__name__}: {exc}",
                )
                for line in unique_lines
            ]

        source_bytes = normalized.encode("utf-8", errors="ignore")
        return [
            AstLocationContext(
                file=target_file,
                line=line,
                available=True,
                scopes=self._scopes_for_line(tree.root_node, source_bytes, line),
                snippet=self._snippet(source_lines, line, context_lines),
                snippet_start_line=self._snippet_start(line, context_lines),
            )
            for line in unique_lines
        ]

    def describe_outline(
        self,
        target_file: str,
        source: str,
        *,
        max_declarations: int = 40,
    ) -> AstOutline:
        """List the declarations of a file without including its full content.

        A test failure is often caused by a file other than the one the stack
        trace points at, so the model needs to know which types and members
        exist elsewhere without paying the token cost of every related file.
        """

        normalized = SyntaxValidator.normalize_transport_bom(source)
        parser = self._extractor._create_parser(Path(target_file).suffix.lower())
        if parser is None:
            return AstOutline(
                file=target_file,
                available=False,
                error="No tree-sitter parser available for this file type.",
            )

        try:
            tree = parser.parse(normalized.encode("utf-8", errors="ignore"))
        except Exception as exc:
            return AstOutline(
                file=target_file,
                available=False,
                error=f"{type(exc).__name__}: {exc}",
            )

        source_bytes = normalized.encode("utf-8", errors="ignore")
        declarations: list[AstScope] = []

        def walk(node) -> None:
            if len(declarations) >= max(int(max_declarations), 1):
                return
            if node.type in _SCOPE_NODE_TYPES:
                declarations.append(
                    AstScope(
                        node_type=node.type,
                        name=self._node_name(node, source_bytes),
                        start_line=int(node.start_point[0]) + 1,
                        end_line=int(node.end_point[0]) + 1,
                    )
                )
            for child in node.children:
                walk(child)

        walk(tree.root_node)
        return AstOutline(file=target_file, available=True, declarations=declarations)

    def _scopes_for_line(self, root, source_bytes: bytes, line: int) -> list[AstScope]:
        scopes: list[AstScope] = []

        def walk(node) -> None:
            start_line = int(node.start_point[0]) + 1
            end_line = int(node.end_point[0]) + 1
            if not (start_line <= line <= end_line):
                return

            if node.type in _SCOPE_NODE_TYPES:
                scopes.append(
                    AstScope(
                        node_type=node.type,
                        name=self._node_name(node, source_bytes),
                        start_line=start_line,
                        end_line=end_line,
                    )
                )

            for child in node.children:
                walk(child)

        walk(root)
        return scopes

    def _node_name(self, node, source_bytes: bytes) -> str | None:
        name_node = node.child_by_field_name("name")
        if name_node is not None:
            text = self._extractor._node_text(source_bytes, name_node).strip()
            if text:
                return text

        for child in node.children:
            if child.type in _NAME_NODE_TYPES:
                text = self._extractor._node_text(source_bytes, child).strip()
                if text:
                    return text
        return None

    @staticmethod
    def _snippet_start(line: int, context_lines: int) -> int:
        return max(line - context_lines, 1)

    @classmethod
    def _snippet(cls, source_lines: list[str], line: int, context_lines: int) -> str:
        if not source_lines:
            return ""
        start = cls._snippet_start(line, context_lines) - 1
        end = min(line + context_lines, len(source_lines))
        numbered = [
            f"{index + 1}: {source_lines[index]}" for index in range(start, end)
        ]
        return "\n".join(numbered)
