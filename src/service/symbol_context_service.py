"""Cross-file symbol context resolved from verification diagnostics.

Verification failures routinely name a symbol that is declared somewhere the
repair model cannot see. A ``CS0534`` ("does not implement inherited abstract
member") names the base type and the exact member signatures, but the repair
prompt only ever contained the failing file, so the model had to guess the
signatures it was required to implement and kept reproducing the same error.

This service closes that gap for every verification stage (syntax, build and
tests): it extracts the symbols named by the diagnostics, finds the repository
files that *declare* them and returns their declaration signatures as
read-only context.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from src.service.ast_context_service import (
    AstContextService,
    declaration_signature_at,
)
from src.service.localizer.constants import _PROGRAMMING_KEYWORDS
from src.service.localizer.discovery import discover_repository_code_files
from src.service.localizer.utils import safe_read_text

#: Diagnostics quote symbols using whichever quotation marks the compiler's
#: locale emits, so every common pairing is accepted.
_QUOTED_SPAN_RE = re.compile(
    r"[\"'\u2018\u2019\u201c\u201d`]"
    r"([^\"'\u2018\u2019\u201c\u201d`\n]{2,200})"
    r"[\"'\u2018\u2019\u201c\u201d`]"
)
_IDENTIFIER_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]{2,}")

#: Keywords that introduce a named declaration across the supported languages.
#: Matching on these is what makes the prescan both cheap and precise: a symbol
#: is only considered declared in a file when it follows one of them, which
#: keeps mere *usages* from being mistaken for definitions.
_DECLARATION_KEYWORDS = (
    "class",
    "interface",
    "struct",
    "record",
    "enum",
    "trait",
    "object",
    "type",
    "typedef",
    "protocol",
    "def",
    "func",
    "fn",
)


@dataclass(frozen=True)
class SymbolDeclaration:
    """A single declaration together with its source signature line."""

    name: str | None
    node_type: str
    start_line: int
    end_line: int
    signature: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "node_type": self.node_type,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "signature": self.signature,
        }


@dataclass
class ResolvedSymbolContext:
    """Where a diagnostic symbol is declared, and with which signatures."""

    symbol: str
    file: str
    declarations: list[SymbolDeclaration] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "file": self.file,
            "declarations": [item.to_dict() for item in self.declarations],
        }


def extract_diagnostic_symbols(messages: Iterable[str]) -> list[str]:
    """Extract symbol names referenced by diagnostic messages, best first.

    Compiler and test-runner messages wrap symbols in quotes and often qualify
    them (``SerializerV2.Deserialize(...)``). Both the qualifier and the member
    are returned, the qualifier first, because the declaring type is what the
    model usually needs to inspect.
    """

    ordered: dict[str, float] = {}

    def record(symbol: str, weight: float) -> None:
        if len(symbol) < 3:
            return
        if weight > ordered.get(symbol, 0.0):
            ordered[symbol] = weight

    for message in messages:
        if not message:
            continue
        for match in _QUOTED_SPAN_RE.finditer(message):
            span = match.group(1)
            # The leading segment of a qualified name is the declaring type.
            for position, segment in enumerate(span.split(".")):
                for identifier in _IDENTIFIER_RE.findall(segment):
                    if identifier.lower() in _PROGRAMMING_KEYWORDS:
                        continue
                    record(identifier, 3.0 if position == 0 else 2.0)

    return [symbol for symbol, _ in sorted(ordered.items(), key=lambda i: (-i[1], i[0]))]


class RepositorySymbolContextService:
    """Locate repository declarations for symbols named by diagnostics."""

    def __init__(
        self,
        max_file_size_bytes: int = 350_000,
        ast_service: AstContextService | None = None,
    ) -> None:
        self.max_file_size_bytes = max_file_size_bytes
        self._ast_service = ast_service or AstContextService()
        self._source_cache: dict[str, list[tuple[str, str]]] = {}

    def _sources_for(self, repo_path: Path) -> list[tuple[str, str]]:
        """Read every discoverable code file once and cache the contents.

        Repair loops resolve context on each round and each round inspects
        several symbols. Re-reading the repository per symbol dominated the
        cost, so the corpus is read once and scanned in memory afterwards.
        """

        key = str(repo_path)
        cached = self._source_cache.get(key)
        if cached is not None:
            return cached

        sources: list[tuple[str, str]] = []
        for rel_path in discover_repository_code_files(repo_path):
            source = safe_read_text(repo_path / rel_path, self.max_file_size_bytes)
            if source:
                sources.append((rel_path, source))

        self._source_cache[key] = sources
        return sources

    @staticmethod
    def _declaration_pattern(symbol: str) -> re.Pattern[str]:
        keywords = "|".join(_DECLARATION_KEYWORDS)
        return re.compile(
            rf"\b(?:{keywords})\s+(?:[A-Za-z_][\w.<>\[\], ]*\s+)?{re.escape(symbol)}\b"
        )

    def _find_declaring_files(
        self, repo_path: Path, symbol: str, limit: int
    ) -> list[str]:
        """Find files that *declare* ``symbol``, best candidate first.

        A plain substring scan would rank any file that merely mentions the
        symbol, which is how an unrelated property beat the abstract class we
        actually needed. Requiring a declaration keyword, and favouring a file
        whose name matches the symbol, keeps the result on the declaration.
        """

        pattern = self._declaration_pattern(symbol)
        lowered = symbol.lower()
        scored: list[tuple[float, str]] = []

        for rel_path, source in self._sources_for(repo_path):
            # Declarations preserve the symbol's spelling, so a case-sensitive
            # membership test is both a valid and a very cheap prefilter.
            if symbol not in source:
                continue
            if not pattern.search(source):
                continue

            score = 1.0
            if Path(rel_path).stem.lower() == lowered:
                score += 5.0
            if "/test" in rel_path.lower() or "spec" in Path(rel_path).stem.lower():
                score -= 2.0
            scored.append((score, rel_path))

        scored.sort(key=lambda item: (-item[0], len(item[1]), item[1]))
        return [rel_path for _, rel_path in scored[:limit]]

    def _declarations_for(
        self,
        repo_path: Path,
        rel_path: str,
        symbol: str,
        max_declarations: int,
    ) -> list[SymbolDeclaration]:
        source = safe_read_text(repo_path / rel_path, self.max_file_size_bytes)
        if not source:
            return []

        outline = self._ast_service.describe_outline(
            rel_path,
            source,
            max_declarations=200,
        )
        if not outline.available:
            return []

        lines = source.splitlines()
        target = symbol.lower()
        matched: list[SymbolDeclaration] = []
        container_spans: list[tuple[int, int]] = []

        for declaration in outline.declarations:
            name = (declaration.name or "").lower()
            if name != target:
                continue
            matched.append(
                SymbolDeclaration(
                    name=declaration.name,
                    node_type=declaration.node_type,
                    start_line=declaration.start_line,
                    end_line=declaration.end_line,
                    signature=self._signature_at(lines, declaration.start_line),
                )
            )
            container_spans.append((declaration.start_line, declaration.end_line))

        if not matched:
            return []

        # When the symbol names a type, its members are the contract the model
        # has to satisfy, so they are included alongside the type itself.
        for declaration in outline.declarations:
            if len(matched) >= max_declarations:
                break
            if (declaration.name or "").lower() == target:
                continue
            if any(
                start < declaration.start_line <= end
                for start, end in container_spans
            ):
                matched.append(
                    SymbolDeclaration(
                        name=declaration.name,
                        node_type=declaration.node_type,
                        start_line=declaration.start_line,
                        end_line=declaration.end_line,
                        signature=self._signature_at(lines, declaration.start_line),
                    )
                )

        return matched[:max_declarations]

    @staticmethod
    def _signature_at(lines: list[str], start_line: int) -> str:
        return declaration_signature_at(lines, start_line)

    def declarations_for_symbol(
        self,
        repo_path: Path | str,
        symbol: str,
        *,
        exclude_files: Iterable[str] = (),
        max_files: int = 1,
        max_declarations: int = 12,
    ) -> list[ResolvedSymbolContext]:
        """Resolve declarations of a single known symbol name.

        ``resolve`` extracts symbols from diagnostic prose; callers that already
        know the symbol need this entry point instead, so they do not have to
        re-quote it into a synthetic message.
        """

        resolved_repo = Path(repo_path)
        if not resolved_repo.is_dir() or not symbol:
            return []

        excluded = {item.replace("\\", "/") for item in exclude_files}
        contexts: list[ResolvedSymbolContext] = []

        for rel_path in self._find_declaring_files(resolved_repo, symbol, limit=3):
            if rel_path in excluded:
                continue
            declarations = self._declarations_for(
                resolved_repo, rel_path, symbol, max_declarations
            )
            if not declarations:
                continue
            contexts.append(
                ResolvedSymbolContext(
                    symbol=symbol,
                    file=rel_path,
                    declarations=declarations,
                )
            )
            if len(contexts) >= max(int(max_files), 1):
                break

        return contexts

    def resolve(
        self,
        repo_path: Path | str,
        messages: Iterable[str],
        *,
        exclude_files: Iterable[str] = (),
        max_symbols: int = 8,
        max_files: int = 6,
        max_declarations: int = 12,
    ) -> list[ResolvedSymbolContext]:
        """Return declaration context for symbols named in ``messages``.

        Files in ``exclude_files`` are skipped because the caller already shows
        their full content to the model.
        """

        resolved_repo = Path(repo_path)
        if not resolved_repo.is_dir():
            return []

        symbols = extract_diagnostic_symbols(messages)
        if not symbols:
            return []

        excluded = {item.replace("\\", "/") for item in exclude_files}
        contexts: list[ResolvedSymbolContext] = []
        seen_files: set[str] = set()

        for symbol in symbols[: max(int(max_symbols), 0)]:
            if len(contexts) >= max_files:
                break

            for rel_path in self._find_declaring_files(resolved_repo, symbol, limit=3):
                if rel_path in excluded or rel_path in seen_files:
                    continue

                declarations = self._declarations_for(
                    resolved_repo, rel_path, symbol, max_declarations
                )
                if not declarations:
                    continue

                seen_files.add(rel_path)
                contexts.append(
                    ResolvedSymbolContext(
                        symbol=symbol,
                        file=rel_path,
                        declarations=declarations,
                    )
                )
                break

        return contexts
