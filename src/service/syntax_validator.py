from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from src.service.localizer.ast.tree_sitter_symbol_extractor import (
    TreeSitterSymbolExtractor,
)


@dataclass
class SyntaxDiagnostic:
    kind: str
    start_line: int
    start_column: int
    end_line: int
    end_column: int
    source_excerpt: str


@dataclass
class SyntaxValidationResult:
    available: bool
    valid: bool
    language_suffix: str
    diagnostics: list[SyntaxDiagnostic] = field(default_factory=list)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SyntaxValidator:
    """Validate source structure with the tree-sitter parsers already in use."""

    def __init__(self) -> None:
        self._extractor = TreeSitterSymbolExtractor()

    @staticmethod
    def normalize_transport_bom(value: str) -> str:
        """Remove a leading byte-order mark before parsing.

        Source files carried through the experiment transport may start with a
        real BOM (``\\ufeff``) or its double-encoded form (``ï»¿``). Tree-sitter
        reports the latter as two syntax errors, which would otherwise make an
        untouched original file look invalid and mask real errors in generated
        code.
        """

        if value.startswith("\ufeff"):
            return value[1:]
        if value.startswith("ï»¿"):
            return value[3:]
        return value

    @staticmethod
    def _excerpt(source_lines: list[str], line: int) -> str:
        if not source_lines:
            return ""
        start = max(line - 1, 0)
        end = min(line + 2, len(source_lines))
        return "\n".join(source_lines[start:end])[:500]

    def validate(
        self,
        target_file: str,
        source: str,
        *,
        max_diagnostics: int = 20,
    ) -> SyntaxValidationResult:
        suffix = Path(target_file).suffix.lower()
        parser = self._extractor._create_parser(suffix)
        if parser is None:
            return SyntaxValidationResult(
                available=False,
                valid=True,
                language_suffix=suffix,
            )

        source = self.normalize_transport_bom(source)
        source_bytes = source.encode("utf-8", errors="ignore")
        try:
            tree = parser.parse(source_bytes)
        except Exception as exc:
            return SyntaxValidationResult(
                available=True,
                valid=False,
                language_suffix=suffix,
                error=f"{type(exc).__name__}: {exc}",
            )

        source_lines = source.splitlines()
        diagnostics: list[SyntaxDiagnostic] = []

        def walk(node) -> None:
            if len(diagnostics) >= max_diagnostics:
                return
            if node.type == "ERROR" or bool(getattr(node, "is_missing", False)):
                start_row, start_column = node.start_point
                end_row, end_column = node.end_point
                diagnostics.append(
                    SyntaxDiagnostic(
                        kind="missing"
                        if bool(getattr(node, "is_missing", False))
                        else "error",
                        start_line=int(start_row) + 1,
                        start_column=int(start_column) + 1,
                        end_line=int(end_row) + 1,
                        end_column=int(end_column) + 1,
                        source_excerpt=self._excerpt(source_lines, int(start_row)),
                    )
                )
            for child in node.children:
                walk(child)

        if bool(getattr(tree.root_node, "has_error", False)):
            walk(tree.root_node)

        return SyntaxValidationResult(
            available=True,
            valid=not bool(getattr(tree.root_node, "has_error", False)),
            language_suffix=suffix,
            diagnostics=diagnostics,
        )
