"""LLM-selected symbol context grounded in mechanically extracted declarations."""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
from pathlib import Path
from typing import Any, Iterable

from src.llm_client.multi_model_llm_client import MultiModelLLMClient
from src.models.utility_decisions import (
    DiagnosticContextSelection,
    DiagnosticSymbols,
    SymbolContextSelection,
)
from src.service.ast_context_service import (
    AstContextService,
    AstOutline,
    declaration_signature_at,
)
from src.service.localizer.discovery import discover_repository_code_files
from src.service.localizer.utils import safe_read_text
from src.service.utility_llm_service import UtilityLlmService

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SymbolDeclaration:
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
    return RepositorySymbolContextService().extract_symbols(messages)


class RepositorySymbolContextService:
    """Let the LLM select context; never let it invent source declarations."""

    def __init__(
        self,
        max_file_size_bytes: int = 350_000,
        ast_service: AstContextService | None = None,
        llm_client: MultiModelLLMClient | None = None,
    ) -> None:
        self.max_file_size_bytes = max_file_size_bytes
        self._ast_service = ast_service or AstContextService()
        self._source_cache: dict[str, list[tuple[str, str]]] = {}
        self._utility = UtilityLlmService(llm_client)
        self._symbol_cache: dict[tuple[str, ...], list[str]] = {}
        self._outline_cache: dict[tuple[str, int], tuple[str, AstOutline]] = {}
        self._inventory_limits: list[dict[str, Any]] = []

    def extract_symbols(self, messages: Iterable[str]) -> list[str]:
        messages = tuple(message for message in messages if message)
        if not messages:
            return []
        if messages not in self._symbol_cache:
            result = self._utility.complete(
                "diagnostic_symbols", DiagnosticSymbols, {"messages": messages}
            )
            if len(set(result.symbols)) != len(result.symbols):
                raise ValueError(
                    "LLM symbol extraction returned duplicate declarations."
                )
            self._symbol_cache[messages] = result.symbols
        return list(self._symbol_cache[messages])

    def _inventory(
        self,
        sources: dict[str, str],
        max_declarations: int = 1200,
        symbols: set[str] | None = None,
    ) -> list[ResolvedSymbolContext]:
        inventory: list[ResolvedSymbolContext] = []
        self._inventory_limits = []
        for path, source in sources.items():
            key = (path, max_declarations)
            cached = self._outline_cache.get(key)
            if cached is None or cached[0] != source:
                outline = self._ast_service.describe_outline(
                    path, source, max_declarations=max_declarations + 1
                )
                self._outline_cache[key] = (source, outline)
            else:
                outline = cached[1]
            if not outline.available:
                self._inventory_limits.append({"file": path, "error": outline.error})
                logger.warning(
                    "Symbol inventory has no AST declarations for %s: %s",
                    path,
                    outline.error,
                )
                continue
            if len(outline.declarations) > max_declarations:
                self._inventory_limits.append(
                    {
                        "file": path,
                        "declaration_limit": max_declarations,
                        "truncated": True,
                    }
                )
            lines = source.splitlines()
            for scope in outline.declarations[:max_declarations]:
                if scope.name is None:
                    continue
                containers = sorted(
                    (
                        parent
                        for parent in outline.declarations
                        if parent.name
                        and parent.start_line <= scope.start_line
                        and (
                            parent.end_line >= scope.end_line
                            or parent.node_type == "file_scoped_namespace_declaration"
                        )
                        and (
                            parent.start_line < scope.start_line
                            or parent.end_line > scope.end_line
                        )
                        and any(
                            kind in parent.node_type
                            for kind in (
                                "namespace",
                                "class",
                                "struct",
                                "record",
                                "interface",
                            )
                        )
                    ),
                    key=lambda parent: (parent.start_line, -parent.end_line),
                )
                qualified = ".".join(
                    [parent.name for parent in containers if parent.name] + [scope.name]
                )
                if (
                    symbols is not None
                    and scope.name not in symbols
                    and qualified not in symbols
                ):
                    continue
                inventory.append(
                    ResolvedSymbolContext(
                        symbol=qualified,
                        file=path,
                        declarations=[
                            SymbolDeclaration(
                                name=scope.name,
                                node_type=scope.node_type,
                                start_line=scope.start_line,
                                end_line=scope.end_line,
                                signature=scope.header or declaration_signature_at(
                                    lines, scope.start_line
                                ),
                            )
                        ],
                    )
                )
        return inventory

    @staticmethod
    def _selected(
        ids: list[int], candidates: list[ResolvedSymbolContext], limit: int
    ) -> list[ResolvedSymbolContext]:
        if len(ids) > limit or len(ids) != len(set(ids)):
            raise ValueError(
                "LLM context selection exceeded its limit or repeated a candidate."
            )
        if any(index < 0 or index >= len(candidates) for index in ids):
            raise ValueError("LLM context selection cited an unknown declaration.")
        return [candidates[index] for index in ids]

    def resolve_candidate_declarations(
        self, sources: dict[str, str], messages: Iterable[str]
    ) -> dict[str, list[ResolvedSymbolContext]]:
        messages = list(dict.fromkeys(messages))
        resolved: dict[str, list[ResolvedSymbolContext]] = {
            message: [] for message in messages
        }
        if not messages or not sources:
            return resolved
        candidates = self._inventory(sources)
        if not candidates:
            return resolved
        for start in range(0, len(candidates), 160):
            page = candidates[start : start + 160]
            for message_start in range(0, len(messages), 32):
                queries = messages[message_start : message_start + 32]
                decision = self._utility.complete(
                    "symbol_context_selection",
                    DiagnosticContextSelection,
                    {
                        "messages": queries,
                        "candidates": [
                            {"candidate_id": index, **item.to_dict()}
                            for index, item in enumerate(page)
                        ],
                        "inventory_limits": self._inventory_limits,
                        "page_start": start,
                        "total_candidates": len(candidates),
                        "max_candidates_per_query": len(page),
                        "request": "Match each diagnostic to its actual declaration candidates. Preserve ambiguity. Do not select reporters, usages, containers or unrelated members.",
                    },
                )
                seen: set[int] = set()
                for match in decision.matches:
                    if (
                        match.message_index >= len(queries)
                        or match.message_index in seen
                    ):
                        raise ValueError(
                            "LLM context selection cited an unknown or duplicate diagnostic."
                        )
                    seen.add(match.message_index)
                    resolved[queries[match.message_index]].extend(
                        self._selected(match.candidate_ids, page, len(page))
                    )
                if len(seen) != len(queries):
                    raise ValueError("LLM context selection omitted a diagnostic.")
        return resolved

    def _sources_for(self, repo_path: Path) -> list[tuple[str, str]]:
        key = str(repo_path)
        if key not in self._source_cache:
            sources = []
            for rel_path in discover_repository_code_files(repo_path):
                source = safe_read_text(repo_path / rel_path, self.max_file_size_bytes)
                if source:
                    sources.append((rel_path, source))
            self._source_cache[key] = sources
        return self._source_cache[key]

    def _declarations_for(
        self, repo_path: Path, rel_path: str, symbol: str, max_declarations: int
    ) -> list[SymbolDeclaration]:
        sources = dict(self._sources_for(repo_path))
        source = sources.get(rel_path)
        if source is None:
            raise ValueError(
                f"Selected symbol file is absent from the source inventory: {rel_path}"
            )
        inventory = self._inventory({rel_path: source})
        matching = [
            item
            for item in inventory
            if item.declarations[0].name == symbol or item.symbol == symbol
        ]
        declarations: list[SymbolDeclaration] = []
        for context in matching:
            owner = context.declarations[0]
            declarations.append(owner)
            declarations.extend(
                item.declarations[0]
                for item in inventory
                if owner.start_line < item.declarations[0].start_line <= owner.end_line
            )
        return list(dict.fromkeys(declarations))[:max_declarations]

    @staticmethod
    def _signature_at(lines: list[str], start_line: int) -> str:
        return declaration_signature_at(lines, start_line)

    def _select_context(
        self,
        repo_path: Path,
        request: dict[str, Any],
        exclude_files: Iterable[str],
        max_files: int,
        max_declarations: int,
    ) -> list[ResolvedSymbolContext]:
        excluded = {item.replace("\\", "/") for item in exclude_files}
        names = (
            self.extract_symbols(request.get("messages", []))[
                : request.get("max_symbols", 8)
            ]
            if "messages" in request
            else [str(request["symbol"])]
        )
        if not names:
            return []
        leaves = {name.replace("::", ".").rsplit(".", 1)[-1] for name in names}
        sources = {
            path: source
            for path, source in self._sources_for(repo_path)
            if path.replace("\\", "/") not in excluded
            and any(name in source for name in leaves)
        }
        candidates = self._inventory(sources, symbols={*names, *leaves})
        if not candidates or max_files <= 0:
            return []

        def select(page: list[ResolvedSymbolContext]) -> list[ResolvedSymbolContext]:
            decision = self._utility.complete(
                "symbol_context_selection",
                SymbolContextSelection,
                {
                    **request,
                    "inventory_limits": self._inventory_limits,
                    "max_file_size_bytes": self.max_file_size_bytes,
                    "retrieval_symbols": names,
                    "limit": min(max_files, len(page)),
                    "candidates": [
                        {"candidate_id": index, **item.to_dict()}
                        for index, item in enumerate(page)
                    ],
                },
            )
            return self._selected(decision.candidate_ids, page, max_files)

        selected = [
            item
            for start in range(0, len(candidates), 160)
            for item in select(candidates[start : start + 160])
        ]
        if len(selected) > max_files:
            selected = select(selected)
        contexts = []
        for candidate in selected:
            contexts.append(
                ResolvedSymbolContext(
                    symbol=candidate.symbol,
                    file=candidate.file,
                    declarations=self._declarations_for(
                        repo_path, candidate.file, candidate.symbol, max_declarations
                    ),
                )
            )
        return contexts

    def declarations_for_symbol(
        self,
        repo_path: Path | str,
        symbol: str,
        *,
        exclude_files: Iterable[str] = (),
        max_files: int = 1,
        max_declarations: int = 12,
    ) -> list[ResolvedSymbolContext]:
        resolved_repo = Path(repo_path)
        if not resolved_repo.is_dir() or not symbol:
            return []
        return self._select_context(
            resolved_repo,
            {"symbol": symbol},
            exclude_files,
            max_files,
            max_declarations,
        )

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
        resolved_repo = Path(repo_path)
        messages = list(messages)
        if not resolved_repo.is_dir() or not messages or max_symbols <= 0:
            return []
        return self._select_context(
            resolved_repo,
            {"messages": messages, "max_symbols": max_symbols},
            exclude_files,
            max_files,
            max_declarations,
        )
