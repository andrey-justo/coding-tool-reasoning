"""SWE MCP tool/context wiring helpers.

This module provides:
- shared server context factory (taxonomy + concern assets)
- helper to register SWE MCP tools onto a FastMCP instance

The FastMCP server instance is created in src.main.
"""

from __future__ import annotations

import glob
import json
import os
from typing import Any, List, Optional

from src.mcp.tools.swe_mcp_tools import register_swe_mcp_tools
from src.models.swe_config import SweMcpConfig
from src.models.swe_server_context import SweServerContext
from src.service.swe_taxonomy_service import SweKnowledgeBase


class SweMcpServerContextProvider:
    """Class-based context provider and MCP wiring for SWE tools."""

    def __init__(self, repo_root: str | None = None) -> None:
        self._repo_root = repo_root or os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..")
        )
        self._server_context: SweServerContext | None = None

    @property
    def repo_root(self) -> str:
        return self._repo_root

    def create_swe_server_context(self, force_reload: bool = False) -> SweServerContext:
        """Load taxonomies and concern assets once and cache server context."""

        if self._server_context is not None and not force_reload:
            return self._server_context

        config = SweMcpConfig.load(repo_root=self._repo_root)

        ground_dir = config.taxonomy.ground_data_dir or os.path.join(
            self._repo_root, "knowledge", "data"
        )
        if not os.path.isabs(ground_dir):
            ground_dir = os.path.join(self._repo_root, ground_dir)

        linked_dir = config.taxonomy.linked_data_dir or os.path.join(
            self._repo_root, "knowledge", "linked_data"
        )
        if not os.path.isabs(linked_dir):
            linked_dir = os.path.join(self._repo_root, linked_dir)

        kb = SweKnowledgeBase(
            ground_data_dir=ground_dir,
            linked_data_dir=linked_dir,
            lazy_load_nodes=config.taxonomy.lazy_load_nodes,
        )
        kb.load()
        templates = self._load_concern_assets(config=config)

        self._server_context = SweServerContext(
            repo_root=self._repo_root,
            config=config,
            kb=kb,
            templates=templates,
        )
        return self._server_context

    def _resolve_path(self, configured_path: str) -> str:
        if os.path.isabs(configured_path):
            return configured_path
        return os.path.join(self._repo_root, configured_path)

    def _load_concern_assets(self, config: SweMcpConfig) -> List[dict]:
        """Load concern templates and concern-group data from knowledge roots."""

        results: List[dict] = []
        swe_concern = config.concern_assets.swe_concern
        swe_subject = config.concern_assets.swe_subject

        data_root = self._resolve_path(
            config.concern_assets.data_root_dir or os.path.join("knowledge", "data"),
        )
        templates_root = self._resolve_path(
            config.concern_assets.templates_root_dir
            or os.path.join("knowledge", "template"),
        )

        concern_templates_dir = os.path.join(templates_root, swe_concern)
        if not os.path.isdir(concern_templates_dir):
            concern_templates_dir = templates_root
        if os.path.isdir(concern_templates_dir):
            for template_path in sorted(
                glob.glob(os.path.join(concern_templates_dir, "*.md"))
            ):
                with open(template_path, "r", encoding="utf-8") as f:
                    results.append(
                        {
                            "kind": "swe_concern_template",
                            "concern": swe_concern,
                            "name": os.path.splitext(os.path.basename(template_path))[
                                0
                            ],
                            "path": template_path,
                            "content": f.read(),
                        }
                    )

        concern_data_dir = os.path.join(data_root, swe_concern)
        if os.path.isdir(concern_data_dir):
            concern_groups = sorted(os.listdir(concern_data_dir))
            if swe_subject:
                concern_groups = [
                    group for group in concern_groups if group == swe_subject
                ]

            for concern_group in concern_groups:
                group_dir = os.path.join(concern_data_dir, concern_group)
                if not os.path.isdir(group_dir):
                    continue
                data_path = os.path.join(group_dir, "data.json")
                if not os.path.exists(data_path):
                    continue

                payload = self._build_concern_data_payload(
                    subject=concern_group,
                    data_path=data_path,
                )
                if not payload:
                    continue

                results.append(
                    {
                        "kind": "swe_concern_data",
                        "concern": swe_concern,
                        "concern_group": concern_group,
                        "name": concern_group,
                        "path": data_path,
                        "content": json.dumps(payload, ensure_ascii=False),
                    }
                )

        return results

    def _build_concern_data_payload(self, subject: str, data_path: str) -> dict:
        payload = self._load_json_payload(data_path)
        if not payload:
            return {}

        if not payload.get("EXAMPLE_DESCRIPTION"):
            payload["EXAMPLE_DESCRIPTION"] = (
                f"{subject.replace('_', ' ').title()} example"
            )
        if not payload.get("DESIGN_PATTERN_NAME"):
            payload["DESIGN_PATTERN_NAME"] = str(
                payload.get("name") or subject.replace("_", " ").title()
            )

        code_example = str(payload.get("CODE_EXAMPLE") or "").strip()
        if not code_example:
            code_example = self._resolve_code_example(subject=subject)
            if code_example:
                payload["CODE_EXAMPLE"] = code_example

        unit_test_example = str(payload.get("UNIT_TEST_EXAMPLE") or "").strip()
        if not unit_test_example:
            unit_test_example = self._extract_unit_test_example(payload)
            if unit_test_example:
                payload["UNIT_TEST_EXAMPLE"] = unit_test_example

        return payload

    @staticmethod
    def _load_json_payload(file_path: str) -> dict:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                payload = json.load(f) or {}
        except (OSError, json.JSONDecodeError):
            return {}
        return payload if isinstance(payload, dict) else {}

    @staticmethod
    def _safe_read_text(file_path: str) -> str:
        if not os.path.exists(file_path):
            return ""
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read().strip()

    def _resolve_code_example(self, subject: str) -> str:
        """Load a subject-specific code example from known repository locations."""

        candidates = [
            os.path.join(self._repo_root, "tests", "examples"),
            os.path.join(self._repo_root, "tests", "reference_code"),
        ]
        for folder in candidates:
            example_path = self._find_first_file_with_stem(folder, subject)
            if example_path:
                return self._safe_read_text(example_path)
        return ""

    def _extract_unit_test_example(self, payload: dict) -> str:
        """Extract unit-test examples only when present in a concern payload."""

        direct_keys = [
            "unit_test_example",
            "unit_test_examples",
            "unit_tests",
            "test_examples",
            "tests",
        ]
        for key in direct_keys:
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
            if isinstance(value, list) and value:
                return "\n".join(f"- {item}" for item in value if str(item).strip())

        return ""

    @staticmethod
    def _find_first_file_with_stem(folder: str, stem: str) -> Optional[str]:
        if not os.path.isdir(folder):
            return None

        for name in sorted(os.listdir(folder)):
            path = os.path.join(folder, name)
            if not os.path.isfile(path):
                continue
            if os.path.splitext(name)[0].lower() == stem.lower():
                return path
        return None

    def register_swe_tools_on_mcp(self, mcp: Any) -> None:
        """Register SWE MCP tools on a provided FastMCP instance."""

        register_swe_mcp_tools(mcp, self.create_swe_server_context)


_DEFAULT_CONTEXT_PROVIDER = SweMcpServerContextProvider()


def create_swe_server_context(force_reload: bool = False) -> SweServerContext:
    """Backwards-compatible function wrapper for creating shared context."""

    return _DEFAULT_CONTEXT_PROVIDER.create_swe_server_context(
        force_reload=force_reload
    )


def register_swe_tools_on_mcp(mcp: Any) -> None:
    """Backwards-compatible function wrapper for MCP registration."""

    _DEFAULT_CONTEXT_PROVIDER.register_swe_tools_on_mcp(mcp)
