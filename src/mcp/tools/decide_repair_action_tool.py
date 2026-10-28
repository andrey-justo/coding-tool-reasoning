from __future__ import annotations

from typing import Any

from src.llm_client.multi_model_llm_client import MultiModelLLMClient
from src.models.repair_agent import RepairAgentDecision
from src.models.utility_decisions import SemanticReview
from src.service.utility_llm_service import UtilityLlmService


class DecideRepairActionTool:
    def __init__(self, registry: Any) -> None:
        self._registry = registry

    def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        client_cls = self._registry._llm_client_cls or MultiModelLLMClient
        decision = UtilityLlmService(client_cls()).complete(
            "repair_agent", RepairAgentDecision, state
        )
        return decision.model_dump()

    def review(self, state: dict[str, Any]) -> dict[str, Any]:
        client_cls = self._registry._llm_client_cls or MultiModelLLMClient
        return UtilityLlmService(client_cls()).complete(
            "repair_review", SemanticReview, state
        ).model_dump()
