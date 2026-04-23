from dataclasses import dataclass
from typing import List

from business_logic.swe_taxonomy_service import SweKnowledgeBase
from models.swe_config import SweMcpConfig


@dataclass
class SweServerContext:
    """Factory-produced context shared by MCP tools.

    Holds the loaded SWE taxonomy (knowledge base) and preloaded templates so
    we don't reload CSVs and files on every tool call.
    """

    repo_root: str
    config: SweMcpConfig
    kb: SweKnowledgeBase
    templates: List[dict]
