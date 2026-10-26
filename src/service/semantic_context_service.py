"""Semantic context for verification diagnostics, resolved with tree-sitter.

AST context proves *where* a diagnostic is, but not *what contract* the failing
expression has to satisfy. A type-mismatch diagnostic names the supplied and the
expected type, yet the repair prompt never carried the signature of the callee
that imposes the expectation, so the model had to guess between a cast, a
pattern test and a signature change.

This service closes that gap without hard-coding any compiler: it resolves the
call site at the diagnostic position, the declarations of the symbols named by
the diagnostic, and the places those symbols are already used. Everything is
derived from tree-sitter grammars, so it works for every language the localizer
already parses instead of a single toolchain.

Declarations are searched in the failing file first. That ordering matters for
chunked repair, where the callee can be declared in a chunk the model is not
being shown, and for the repository resolver, which deliberately skips files
whose full content is already in the prompt.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from src.service.ast_context_service import AstContextService, declaration_signature_at
from src.service.localizer.ast.tree_sitter_symbol_extractor import (
    TreeSitterSymbolExtractor,
)
from src.service.symbol_context_service import extract_diagnostic_symbols
from src.service.syntax_validator import SyntaxValidator

#: Call-like constructs across the supported grammars. Resolving the call site
#: is what links an argument diagnostic to the signature that rejected it.
_CALL_NODE_TYPES = {
    "invocation_expression",
    "object_creation_expression",
    "implicit_object_creation_expression",
    "call_expression",
    "call",
    "method_invocation",
    "new_expression",
    "macro_invocation",
}

#: Grammars disagree on which field holds the callee, so each is tried in turn.
_CALLEE_FIELDS = ("function", "name", "constructor", "type")

_IDENTIFIER_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")

#: Declarations that define a callable or type contract. Usages of other node
#: kinds are still reported, but these are what carry a signature.
_CONTRACT_NODE_HINTS = (
    "method",
    "function",
    "constructor",
    "class",
    "interface",
    "struct",
    "record",
    "enum",
    "type",
)


@dataclass(frozen=True)
class SymbolUsage:
    """One line where a symbol is already used in the failing file."""

    line: int
    snippet: str

    def to_dict(self) -> dict[str, Any]:
        return {"line": self.line, "snippet": self.snippet}


@dataclass
class SemanticSymbolContext:
    """Where a diagnostic symbol is declared and how it is already used."""

    symbol: str
    origin: str
    file: str | None = None
    declarations: list[dict[str, Any]] = field(default_factory=list)
    usages: list[SymbolUsage] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "origin": self.origin,
            "file": self.file,
            "declarations": self.declarations,
            "usages": [usage.to_dict() for usage in self.usages],
        }


@dataclass
class CallSiteContext:
    """The call expression that a diagnostic position falls inside."""

    line: int
    column: int
    expression: str
    callee: str | None
    arguments: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "line": self.line,
            "column": self.column,
            "expression": self.expression,
            "callee": self.callee,
            "arguments": self.arguments,
        }


@dataclass
class DiagnosticSemanticContext:
    """Semantic evidence assembled for a single diagnostic."""

    line: int
    code: str
    message: str
    available: bool
    call_site: CallSiteContext | None = None
    symbols: list[SemanticSymbolContext] = field(default_factory=list)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "line": self.line,
            "code": self.code,
            "message": self.message,
            "available": self.available,
            "call_site": self.call_site.to_dict() if self.call_site else None,
            "symbols": [symbol.to_dict() for symbol in self.symbols],
            "error": self.error,
        }


class SemanticContextService:
    """Resolve call sites and symbol contracts behind verification diagnostics."""

    def __init__(
        self,
        extractor: TreeSitterSymbolExtractor | None = None,
        ast_service: AstContextService | None = None,
    ) -> None:
        self._extractor = extractor or TreeSitterSymbolExtractor()
        self._ast_service = ast_service or AstContextService(self._extractor)

    def describe(
        self,
        target_file: str,
        source: str,
        diagnostics: Iterable[dict[str, Any]],
        *,
        repo_path: Path | str | None = None,
        symbol_resolver: Any = None,
        exclude_files: Iterable[str] = (),
        max_diagnostics: int = 6,
        max_symbols: int = 6,
        max_usages: int = 3,
    ) -> list[DiagnosticSemanticContext]:
        """Describe the semantics behind each distinct diagnostic position."""

        selected = self._select_diagnostics(diagnostics, max(int(max_diagnostics), 1))
        if not selected:
            return []

        normalized = SyntaxValidator.normalize_transport_bom(source)
        source_lines = normalized.splitlines()
        source_bytes = normalized.encode("utf-8", errors="ignore")
        root, parse_error = self._parse(target_file, source_bytes)

        outline = self._ast_service.describe_outline(
            target_file,
            normalized,
            max_declarations=400,
        )
        local_declarations = outline.declarations if outline.available else []

        contexts: list[DiagnosticSemanticContext] = []
        for diagnostic in selected:
            line = self._as_int(diagnostic.get("line"))
            column = self._as_int(diagnostic.get("column"))
            message = str(diagnostic.get("message") or "")

            call_site = None
            if root is not None and line:
                call_site = self._call_site(root, source_bytes, line, column)

            symbols = self._resolve_symbols(
                target_file=target_file,
                source_lines=source_lines,
                local_declarations=local_declarations,
                message=message,
                call_site=call_site,
                repo_path=repo_path,
                symbol_resolver=symbol_resolver,
                exclude_files=exclude_files,
                max_symbols=max(int(max_symbols), 1),
                max_usages=max(int(max_usages), 0),
            )

            contexts.append(
                DiagnosticSemanticContext(
                    line=line,
                    code=str(diagnostic.get("code") or ""),
                    message=message,
                    available=root is not None,
                    call_site=call_site,
                    symbols=symbols,
                    error=parse_error,
                )
            )

        return contexts

    def _parse(self, target_file: str, source_bytes: bytes):
        parser = self._extractor._create_parser(Path(target_file).suffix.lower())
        if parser is None:
            return None, "No tree-sitter parser available for this file type."
        try:
            return parser.parse(source_bytes).root_node, None
        except Exception as exc:  # pragma: no cover - defensive
            return None, f"{type(exc).__name__}: {exc}"

    @staticmethod
    def _as_int(value: Any) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    @classmethod
    def _select_diagnostics(
        cls,
        diagnostics: Iterable[dict[str, Any]],
        limit: int,
    ) -> list[dict[str, Any]]:
        """Keep one diagnostic per position so repeated errors cost one slot."""

        selected: list[dict[str, Any]] = []
        seen: set[tuple[int, int, str]] = set()
        for diagnostic in diagnostics:
            if not isinstance(diagnostic, dict):
                continue
            key = (
                cls._as_int(diagnostic.get("line")),
                cls._as_int(diagnostic.get("column")),
                str(diagnostic.get("code") or ""),
            )
            if key in seen:
                continue
            seen.add(key)
            selected.append(diagnostic)
            if len(selected) >= limit:
                break
        return selected

    def _call_site(
        self,
        root,
        source_bytes: bytes,
        line: int,
        column: int,
    ) -> CallSiteContext | None:
        node = self._find_call_node(root, line, column)
        if node is None:
            return None

        callee_node = None
        for field_name in _CALLEE_FIELDS:
            try:
                callee_node = node.child_by_field_name(field_name)
            except Exception:  # pragma: no cover - grammar without the field
                callee_node = None
            if callee_node is not None:
                break
        if callee_node is None and node.children:
            callee_node = node.children[0]

        callee_text = (
            self._extractor._node_text(source_bytes, callee_node).strip()
            if callee_node is not None
            else ""
        )
        identifiers = _IDENTIFIER_RE.findall(callee_text)

        return CallSiteContext(
            line=line,
            column=column,
            expression=self._truncate(
                self._extractor._node_text(source_bytes, node).strip()
            ),
            callee=identifiers[-1] if identifiers else None,
            arguments=self._arguments(node, source_bytes),
        )

    def _arguments(self, node, source_bytes: bytes) -> list[str]:
        try:
            arguments_node = node.child_by_field_name("arguments")
        except Exception:  # pragma: no cover - grammar without the field
            arguments_node = None
        if arguments_node is None:
            return []
        return [
            self._truncate(
                self._extractor._node_text(source_bytes, child).strip(), limit=160
            )
            for child in arguments_node.named_children
        ]

    def _find_call_node(self, root, line: int, column: int):
        """Return the innermost call containing the diagnostic position."""

        row = max(line - 1, 0)
        col = max(column - 1, 0)
        best = None

        def contains(node) -> bool:
            start_row, start_col = node.start_point
            end_row, end_col = node.end_point
            if (start_row, start_col) > (row, col):
                return False
            return (end_row, end_col) >= (row, col)

        def walk(node) -> None:
            nonlocal best
            if not contains(node):
                return
            if node.type in _CALL_NODE_TYPES:
                best = node
            for child in node.children:
                walk(child)

        walk(root)
        if best is not None:
            return best

        # A diagnostic column can point past the call it refers to, so the line
        # alone is used as a fallback anchor before giving up.
        fallback = None

        def walk_line(node) -> None:
            nonlocal fallback
            if node.start_point[0] > row or node.end_point[0] < row:
                return
            if node.type in _CALL_NODE_TYPES and fallback is None:
                fallback = node
            for child in node.children:
                walk_line(child)

        walk_line(root)
        return fallback

    def _resolve_symbols(
        self,
        *,
        target_file: str,
        source_lines: list[str],
        local_declarations: list[Any],
        message: str,
        call_site: CallSiteContext | None,
        repo_path: Path | str | None,
        symbol_resolver: Any,
        exclude_files: Iterable[str],
        max_symbols: int,
        max_usages: int,
    ) -> list[SemanticSymbolContext]:
        ordered: list[str] = []
        if call_site and call_site.callee:
            ordered.append(call_site.callee)
        for symbol in extract_diagnostic_symbols([message]):
            if symbol not in ordered:
                ordered.append(symbol)

        resolved: list[SemanticSymbolContext] = []
        for symbol in ordered[:max_symbols]:
            declarations = self._local_declarations(
                symbol, local_declarations, source_lines
            )
            if declarations:
                resolved.append(
                    SemanticSymbolContext(
                        symbol=symbol,
                        origin="target_file",
                        file=target_file,
                        declarations=declarations,
                        usages=self._usages(symbol, source_lines, max_usages),
                    )
                )
                continue

            repository = self._repository_declarations(
                symbol=symbol,
                repo_path=repo_path,
                symbol_resolver=symbol_resolver,
                exclude_files=exclude_files,
            )
            if repository is not None:
                resolved.append(repository)
                continue

            # An unresolved symbol is still evidence: it tells the model the
            # declaration lives outside the repository, so the contract has to
            # be honoured rather than redefined.
            resolved.append(
                SemanticSymbolContext(
                    symbol=symbol,
                    origin="external_or_unresolved",
                    usages=self._usages(symbol, source_lines, max_usages),
                )
            )

        return resolved

    @staticmethod
    def _local_declarations(
        symbol: str,
        declarations: list[Any],
        source_lines: list[str],
    ) -> list[dict[str, Any]]:
        """Return every same-file declaration of ``symbol``, overloads included."""

        target = symbol.lower()
        matched: list[dict[str, Any]] = []
        for declaration in declarations:
            if (declaration.name or "").lower() != target:
                continue
            matched.append(
                {
                    "name": declaration.name,
                    "node_type": declaration.node_type,
                    "start_line": declaration.start_line,
                    "end_line": declaration.end_line,
                    "signature": declaration_signature_at(
                        source_lines, declaration.start_line
                    ),
                    "defines_contract": any(
                        hint in declaration.node_type for hint in _CONTRACT_NODE_HINTS
                    ),
                }
            )
        return matched

    @staticmethod
    def _repository_declarations(
        *,
        symbol: str,
        repo_path: Path | str | None,
        symbol_resolver: Any,
        exclude_files: Iterable[str],
    ) -> SemanticSymbolContext | None:
        if repo_path is None or symbol_resolver is None:
            return None
        try:
            contexts = symbol_resolver.declarations_for_symbol(
                repo_path,
                symbol,
                exclude_files=exclude_files,
            )
        except Exception:  # pragma: no cover - defensive
            return None
        if not contexts:
            return None

        resolved = contexts[0]
        return SemanticSymbolContext(
            symbol=symbol,
            origin="repository",
            file=resolved.file,
            declarations=[item.to_dict() for item in resolved.declarations],
        )

    @classmethod
    def _usages(
        cls,
        symbol: str,
        source_lines: list[str],
        max_usages: int,
    ) -> list[SymbolUsage]:
        if max_usages <= 0:
            return []
        pattern = re.compile(rf"\b{re.escape(symbol)}\b")
        usages: list[SymbolUsage] = []
        for index, text in enumerate(source_lines):
            if not pattern.search(text):
                continue
            usages.append(
                SymbolUsage(line=index + 1, snippet=cls._truncate(text.strip(), 200))
            )
            if len(usages) >= max_usages:
                break
        return usages

    @staticmethod
    def _truncate(value: str, limit: int = 400) -> str:
        collapsed = " ".join(value.split())
        if len(collapsed) <= limit:
            return collapsed
        return collapsed[:limit] + " ..."
