from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Iterable

from src.service.localizer.models import LocalizationHit
from src.service.localizer.utils import extract_symbols, safe_read_text


class SymbolImpactStrategy:
    """Estimate refactor impact using symbol definitions/references across files."""

    name = "symbol_impact"

    def __init__(self, max_file_size_bytes: int = 350_000) -> None:
        self.max_file_size_bytes = max_file_size_bytes

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

    def score(
        self,
        repo_path: Path,
        issue_text: str,
        candidate_paths: Iterable[str],
    ) -> dict[str, LocalizationHit]:
        target_symbols = {s.lower() for s in extract_symbols(issue_text)}
        if not target_symbols:
            return {}

        defs_by_file: dict[str, set[str]] = {}
        refs_by_file: dict[str, set[str]] = {}
        imports_by_file: dict[str, set[str]] = {}

        for rel_path in candidate_paths:
            abs_path = repo_path / rel_path
            source = safe_read_text(abs_path, self.max_file_size_bytes)
            if not source:
                continue

            if Path(rel_path).suffix.lower() == ".py":
                defs, refs, imports = self._collect_python_symbols(source)
            else:
                defs, refs, imports = self._collect_generic_symbols(source)

            defs_by_file[rel_path] = defs
            refs_by_file[rel_path] = refs
            imports_by_file[rel_path] = imports

        if not defs_by_file:
            return {}

        seed_files = {
            rel_path
            for rel_path, defs in defs_by_file.items()
            if defs.intersection(target_symbols)
        }
        seed_files.update(
            {
                rel_path
                for rel_path, refs in refs_by_file.items()
                if refs.intersection(target_symbols)
            }
        )

        seed_definitions: set[str] = set()
        for rel_path in seed_files:
            seed_definitions.update(defs_by_file.get(rel_path, set()))

        results: dict[str, LocalizationHit] = {}
        for rel_path in defs_by_file.keys():
            definition_overlap = defs_by_file.get(rel_path, set()).intersection(target_symbols)
            direct_overlap = refs_by_file.get(rel_path, set()).intersection(target_symbols)
            impact_overlap = refs_by_file.get(rel_path, set()).intersection(seed_definitions)
            import_overlap = imports_by_file.get(rel_path, set()).intersection(target_symbols)

            score = 0.0
            reasons: list[str] = []

            if definition_overlap:
                score += 8.0 + 2.0 * len(definition_overlap)
                reasons.append(
                    "defines target symbols: "
                    + ", ".join(sorted(definition_overlap)[:8])
                )

            if direct_overlap:
                score += 6.0 + 2.0 * len(direct_overlap)
                reasons.append(
                    "direct symbol refs: " + ", ".join(sorted(direct_overlap)[:8])
                )

            if impact_overlap:
                score += min(10.0, 1.5 * len(impact_overlap))
                reasons.append(
                    "depends on seed defs: " + ", ".join(sorted(impact_overlap)[:8])
                )

            if import_overlap:
                score += min(5.0, float(len(import_overlap)))
                reasons.append(
                    "imports related symbols: " + ", ".join(sorted(import_overlap)[:8])
                )

            if score > 0:
                results[rel_path] = LocalizationHit(
                    path=rel_path,
                    score=score,
                    reasons=reasons,
                )

        return results
