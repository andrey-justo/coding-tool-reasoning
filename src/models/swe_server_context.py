from dataclasses import dataclass
from typing import List

from src.models.swe_config import SweMcpConfig
from src.service.swe_taxonomy_service import SweKnowledgeBase


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
