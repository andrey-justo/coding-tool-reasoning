from __future__ import annotations

import ast
import hashlib
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from src.service.localizer.models import LocalizationHit
from src.service.localizer.utils import (
    count_token_frequency,
    extract_symbols,
    safe_read_text,
)


@dataclass
class _GraphIndex:
    docs_tf: dict[str, dict[str, int]]
    doc_freq: dict[str, int]
    definitions_by_file: dict[str, set[str]]
    references_by_file: dict[str, set[str]]
    neighbors: dict[str, set[str]]


@dataclass
class _IndexedDocument:
    mtime_ns: int
    size: int
    tf: dict[str, int]
    definitions: set[str]
    references: set[str]
    imports: set[str]


class GraphMemoryRelationshipStrategy:
    """Graph + vector-memory reranking strategy for repository localization.

    The strategy builds an in-memory index that combines:
    - lightweight vector similarity (TF-IDF cosine) between issue text and files
    - symbol and import relationships propagated as graph neighborhoods

    This preserves Graphify-like graph-first retrieval behavior while staying
    deterministic and avoiding additional LLM calls during localization.
    """

    name = "graph_memory"

    def __init__(
        self,
        max_file_size_bytes: int = 350_000,
        hops: int = 2,
        semantic_index_dir: str = ".semantic_index",
        persist_semantic_index: bool = True,
        vector_backend: str = "local_tfidf",
    ) -> None:
        self.max_file_size_bytes = max_file_size_bytes
        self.hops = max(1, hops)
        self.semantic_index_dir = semantic_index_dir
        self.persist_semantic_index = persist_semantic_index
        self.vector_backend = vector_backend
        self._cache_key: tuple[str, tuple[str, ...]] | None = None
        self._cache_index: _GraphIndex | None = None
        self._documents_cache: dict[str, _IndexedDocument] = {}

    def _index_file_path(self, repo_path: Path) -> Path:
        index_root = repo_path / self.semantic_index_dir
        return index_root / "localizer_graph_memory_index.json"

    def _load_persisted_index(self, repo_path: Path) -> dict[str, _IndexedDocument]:
        if not self.persist_semantic_index:
            return {}

        index_file = self._index_file_path(repo_path)
        if not index_file.exists():
            return {}

        try:
            payload = json.loads(index_file.read_text(encoding="utf-8"))
            if payload.get("version") != 1:
                return {}

            docs = payload.get("documents")
            if not isinstance(docs, dict):
                return {}

            loaded: dict[str, _IndexedDocument] = {}
            for rel_path, value in docs.items():
                if not isinstance(value, dict):
                    continue
                loaded[rel_path] = _IndexedDocument(
                    mtime_ns=int(value.get("mtime_ns", 0)),
                    size=int(value.get("size", 0)),
                    tf={
                        str(token): int(freq)
                        for token, freq in dict(value.get("tf") or {}).items()
                    },
                    definitions={str(v) for v in list(value.get("definitions") or [])},
                    references={str(v) for v in list(value.get("references") or [])},
                    imports={str(v) for v in list(value.get("imports") or [])},
                )
            return loaded
        except Exception:
            return {}

    def _save_persisted_index(
        self,
        repo_path: Path,
        documents: dict[str, _IndexedDocument],
    ) -> None:
        if not self.persist_semantic_index:
            return

        index_file = self._index_file_path(repo_path)
        index_file.parent.mkdir(parents=True, exist_ok=True)

        payload = {
            "version": 1,
            "vector_backend": self.vector_backend,
            "documents": {
                rel_path: {
                    "mtime_ns": doc.mtime_ns,
                    "size": doc.size,
                    "tf": doc.tf,
                    "definitions": sorted(doc.definitions),
                    "references": sorted(doc.references),
                    "imports": sorted(doc.imports),
                }
                for rel_path, doc in documents.items()
            },
        }
        index_file.write_text(
            json.dumps(payload, ensure_ascii=True, separators=(",", ":")),
            encoding="utf-8",
        )

    def _read_document(
        self,
        repo_path: Path,
        rel_path: str,
        persisted_docs: dict[str, _IndexedDocument],
    ) -> _IndexedDocument | None:
        abs_path = repo_path / rel_path
        try:
            stat = abs_path.stat()
        except OSError:
            return None

        if stat.st_size > self.max_file_size_bytes:
            return None

        cached = persisted_docs.get(rel_path)
        if (
            cached is not None
            and cached.mtime_ns == stat.st_mtime_ns
            and cached.size == stat.st_size
        ):
            return cached

        source = safe_read_text(abs_path, self.max_file_size_bytes)
        if not source:
            return None

        tf = count_token_frequency(source)
        if Path(rel_path).suffix.lower() == ".py":
            definitions, references, imports = self._collect_python_symbols(source)
        else:
            definitions, references, imports = self._collect_generic_symbols(source)

        return _IndexedDocument(
            mtime_ns=stat.st_mtime_ns,
            size=stat.st_size,
            tf=tf,
            definitions=definitions,
            references=references,
            imports=imports,
        )

    @staticmethod
    def _idf(num_docs: int, doc_freq: int) -> float:
        return math.log((1 + num_docs) / (1 + doc_freq)) + 1.0

    @staticmethod
    def _cosine(left: dict[str, float], right: dict[str, float]) -> float:
        if not left or not right:
            return 0.0

        dot = 0.0
        for token, value in left.items():
            dot += value * right.get(token, 0.0)

        left_norm = math.sqrt(sum(v * v for v in left.values()))
        right_norm = math.sqrt(sum(v * v for v in right.values()))
        if left_norm == 0.0 or right_norm == 0.0:
            return 0.0
        return dot / (left_norm * right_norm)

    @staticmethod
    def _collect_python_symbols(source: str) -> tuple[set[str], set[str], set[str]]:
        definitions: set[str] = set()
        references: set[str] = set()
        imports: set[str] = set()

        try:
            tree = ast.parse(source)
        except SyntaxError:
            return definitions, references, imports

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                definitions.add(node.name.lower())
            elif isinstance(node, ast.Name):
                references.add(node.id.lower())
            elif isinstance(node, ast.Attribute):
                references.add(node.attr.lower())
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name.split(".")[-1].lower())
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.add(node.module.split(".")[-1].lower())
                for alias in node.names:
                    imports.add(alias.name.split(".")[-1].lower())

        return definitions, references, imports

    @staticmethod
    def _collect_generic_symbols(source: str) -> tuple[set[str], set[str], set[str]]:
        definitions = {
            token.lower()
            for token in re.findall(
                r"\b(?:class|interface|struct|enum|def|function)\s+([A-Za-z_][A-Za-z0-9_]*)",
                source,
            )
        }
        references = {
            token.lower()
            for token in re.findall(r"\b([A-Za-z_][A-Za-z0-9_]*)\b", source)
        }
        imports = {
            token.lower()
            for token in re.findall(
                r"\b(?:import|include|require|using|from)\s+([A-Za-z_][A-Za-z0-9_\.]*)",
                source,
            )
        }
        return definitions, references, imports

    def _build_index(self, repo_path: Path, candidate_paths: list[str]) -> _GraphIndex:
        normalized_candidates = tuple(sorted(set(candidate_paths)))
        key_digest = hashlib.sha1(
            "\n".join(normalized_candidates).encode("utf-8", errors="ignore")
        ).hexdigest()
        cache_key = (str(repo_path.resolve()), (key_digest,))
        if self._cache_key == cache_key and self._cache_index is not None:
            return self._cache_index

        persisted_docs = self._load_persisted_index(repo_path)
        changed = False

        docs_tf: dict[str, dict[str, int]] = {}
        doc_freq: dict[str, int] = {}
        definitions_by_file: dict[str, set[str]] = {}
        references_by_file: dict[str, set[str]] = {}
        imports_by_file: dict[str, set[str]] = {}

        for rel_path in normalized_candidates:
            doc = self._read_document(repo_path, rel_path, persisted_docs)
            if doc is None:
                continue

            previous = persisted_docs.get(rel_path)
            if previous != doc:
                persisted_docs[rel_path] = doc
                changed = True

            if doc.tf:
                docs_tf[rel_path] = doc.tf
                for token in doc.tf.keys():
                    doc_freq[token] = doc_freq.get(token, 0) + 1

            definitions_by_file[rel_path] = doc.definitions
            references_by_file[rel_path] = doc.references
            imports_by_file[rel_path] = doc.imports

        symbol_owners: dict[str, set[str]] = {}
        for rel_path, definitions in definitions_by_file.items():
            for symbol in definitions:
                symbol_owners.setdefault(symbol, set()).add(rel_path)

        neighbors: dict[str, set[str]] = {
            rel_path: set() for rel_path in definitions_by_file.keys()
        }

        for rel_path in definitions_by_file.keys():
            linked_symbols = set()
            linked_symbols.update(imports_by_file.get(rel_path, set()))
            linked_symbols.update(references_by_file.get(rel_path, set()))

            for symbol in linked_symbols:
                for owner in symbol_owners.get(symbol, set()):
                    if owner == rel_path:
                        continue
                    neighbors[rel_path].add(owner)
                    neighbors.setdefault(owner, set()).add(rel_path)

        index = _GraphIndex(
            docs_tf=docs_tf,
            doc_freq=doc_freq,
            definitions_by_file=definitions_by_file,
            references_by_file=references_by_file,
            neighbors=neighbors,
        )
        self._cache_key = cache_key
        self._cache_index = index
        self._documents_cache = persisted_docs
        if changed:
            self._save_persisted_index(repo_path, persisted_docs)
        return index

    def score(
        self,
        repo_path: Path,
        issue_text: str,
        candidate_paths: Iterable[str],
    ) -> dict[str, LocalizationHit]:
        paths = list(candidate_paths)
        if not paths:
            return {}

        issue_tf = count_token_frequency(issue_text)
        issue_symbols = {symbol.lower() for symbol in extract_symbols(issue_text)}
        if not issue_tf and not issue_symbols:
            return {}

        index = self._build_index(repo_path, paths)
        if not index.docs_tf and not index.definitions_by_file:
            return {}

        num_docs = max(1, len(index.docs_tf))
        issue_vector: dict[str, float] = {}
        for token, freq in issue_tf.items():
            issue_vector[token] = float(freq) * self._idf(
                num_docs,
                index.doc_freq.get(token, 0),
            )

        results: dict[str, LocalizationHit] = {}
        seed_files: set[str] = set()

        for rel_path in paths:
            score = 0.0
            reasons: list[str] = []

            tf = index.docs_tf.get(rel_path)
            if tf and issue_vector:
                doc_vector: dict[str, float] = {}
                for token, freq in tf.items():
                    doc_vector[token] = float(freq) * self._idf(
                        num_docs,
                        index.doc_freq.get(token, 0),
                    )
                cosine = self._cosine(issue_vector, doc_vector)
                if cosine > 0.0:
                    cosine_score = min(18.0, cosine * 30.0)
                    score += cosine_score
                    reasons.append(f"vector similarity cosine={cosine:.4f}")
                    if cosine >= 0.04:
                        seed_files.add(rel_path)

            def_overlap = index.definitions_by_file.get(rel_path, set()).intersection(
                issue_symbols
            )
            ref_overlap = index.references_by_file.get(rel_path, set()).intersection(
                issue_symbols
            )

            if def_overlap:
                score += min(12.0, 2.0 * len(def_overlap))
                reasons.append(
                    "defines issue symbols: " + ", ".join(sorted(def_overlap)[:8])
                )
                seed_files.add(rel_path)

            if ref_overlap:
                score += min(8.0, 1.5 * len(ref_overlap))
                reasons.append("references issue symbols: " + ", ".join(sorted(ref_overlap)[:8]))
                seed_files.add(rel_path)

            if score > 0.0:
                results[rel_path] = LocalizationHit(
                    path=rel_path,
                    score=score,
                    reasons=reasons,
                )

        if not seed_files:
            return results

        frontier = set(seed_files)
        visited = set(seed_files)
        for hop in range(1, self.hops + 1):
            next_frontier: set[str] = set()
            propagation_score = 7.0 / float(hop + 1)
            for node in frontier:
                for neighbor in index.neighbors.get(node, set()):
                    if neighbor in visited:
                        continue
                    visited.add(neighbor)
                    next_frontier.add(neighbor)

                    hit = results.get(neighbor)
                    if hit is None:
                        hit = LocalizationHit(path=neighbor, score=0.0, reasons=[])
                        results[neighbor] = hit

                    hit.score += propagation_score
                    hit.reasons.append(
                        f"graph hop {hop} from related file via symbol relationship"
                    )

            if not next_frontier:
                break
            frontier = next_frontier

        return results
