"""MCP server exposing SWE/NFR context for code generation.

This server:
- Loads SWE taxonomies from taxonomies/ground_data and taxonomies/linked_data
- Provides a planning tool for code generation tasks
- Provides a context tool that returns prompt-ready SWE injections and templates

Run directly for stdio transport:
    python -m src.swe_mcp_server
Or, if using the MCP CLI:
    uv run mcp dev src/swe_mcp_server.py
"""

from __future__ import annotations

import os
from typing import List

from mcp.server.fastmcp import FastMCP

from business_logic.swe_taxonomy_service import SweKnowledgeBase
from models.swe_config import SweMcpConfig
from models.swe_server_context import SweServerContext
from tools.swe_mcp_tools import register_swe_mcp_tools


mcp = FastMCP("SWE-NFR-MCP", json_response=True)


_SERVER_CONTEXT: SweServerContext | None = None


def create_swe_server_context(force_reload: bool = False) -> SweServerContext:
    """Factory for server context: loads taxonomies and templates once.

    Agents/tools should call this to obtain a shared context instead of
    touching the filesystem directly.
    """

    global _SERVER_CONTEXT
    if _SERVER_CONTEXT is not None and not force_reload:
        return _SERVER_CONTEXT

    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

    # Load configuration (taxonomy locations, planning/judging behavior,
    # workflow stages, etc.).
    config = SweMcpConfig.load(repo_root=repo_root)

    # Resolve taxonomy directory paths: use config values if provided,
    # otherwise default to taxonomies/ under repo_root. Convert relative
    # paths to absolute.
    ground_dir = config.taxonomy.ground_data_dir or os.path.join(
        repo_root, "taxonomies", "ground_data"
    )
    if not os.path.isabs(ground_dir):
        ground_dir = os.path.join(repo_root, ground_dir)

    linked_dir = config.taxonomy.linked_data_dir or os.path.join(
        repo_root, "taxonomies", "linked_data"
    )
    if not os.path.isabs(linked_dir):
        linked_dir = os.path.join(repo_root, linked_dir)

    kb = SweKnowledgeBase(
        ground_data_dir=ground_dir,
        linked_data_dir=linked_dir,
    )
    kb.load()
    templates = _load_reliability_templates(repo_root)

    _SERVER_CONTEXT = SweServerContext(
        repo_root=repo_root,
        config=config,
        kb=kb,
        templates=templates,
    )
    return _SERVER_CONTEXT


def _load_reliability_templates(repo_root: str) -> List[dict]:
    """Load reliability-related templates for additional requirements.

    This scans templates/reliability and returns a lightweight summary so
    clients can choose which ones to use in their prompts.
    """

    results: List[dict] = []
    reliability_root = os.path.join(repo_root, "templates", "reliability")
    if not os.path.isdir(reliability_root):
        return results

    # Base prompt templates
    base_template_path = os.path.join(reliability_root, "base_template.md")
    test_template_path = os.path.join(reliability_root, "test_base_template.md")

    if os.path.exists(base_template_path):
        with open(base_template_path, "r", encoding="utf-8") as f:
            results.append(
                {
                    "kind": "reliability_base_prompt",
                    "name": "Reliability Base Template",
                    "path": base_template_path,
                    "content": f.read(),
                }
            )

    if os.path.exists(test_template_path):
        with open(test_template_path, "r", encoding="utf-8") as f:
            results.append(
                {
                    "kind": "reliability_test_prompt",
                    "name": "Reliability Test Template",
                    "path": test_template_path,
                    "content": f.read(),
                }
            )

    # Pattern-specific JSON design templates
    for name in os.listdir(reliability_root):
        pattern_dir = os.path.join(reliability_root, name)
        if not os.path.isdir(pattern_dir):
            continue
        base_design = os.path.join(pattern_dir, "base_design.json")
        if os.path.exists(base_design):
            with open(base_design, "r", encoding="utf-8") as f:
                results.append(
                    {
                        "kind": "reliability_pattern_design",
                        "pattern": name,
                        "path": base_design,
                        "content": f.read(),
                    }
                )

    return results


# Register MCP tools defined under src/tools
register_swe_mcp_tools(mcp, create_swe_server_context)


def main() -> None:
    """Entry point for running the MCP server directly."""

    mcp.run()


if __name__ == "__main__":
    main()
