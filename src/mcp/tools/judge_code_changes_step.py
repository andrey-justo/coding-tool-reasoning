from typing import Any, Optional

from src.llm_client.multi_model_llm_client import MultiModelLLMClient
from src.models.swe_config import SweMcpConfig
from src.models.swe_context import SweContext
from src.models.swe_explanation import SweCodeChangeExplanation
from src.service.explanation_service import ExplanationService
from src.service.swe_knowledge_base_service import SweKnowledgeBase


class JudgeCodeChangesStep:
    """Judge & explain code changes using the SWE knowledge base and an LLM.

    This class is a lightweight wrapper around :class:`ExplanationService`
    so it can be plugged into higher-level workflows or agents. It does
    not depend on agent_framework and can be called directly.
    """

    def __init__(
        self,
        kb: Optional[SweKnowledgeBase] = None,
        llm_client: Optional[MultiModelLLMClient] = None,
        config: Optional[SweMcpConfig] = None,
        ground_data_dir: Optional[str] = None,
        linked_data_dir: Optional[str] = None,
    ) -> None:
        self.config = config or SweMcpConfig()
        if kb is None:
            if not ground_data_dir or not linked_data_dir:
                raise ValueError(
                    "Either 'kb' must be provided or both 'ground_data_dir' "
                    "and 'linked_data_dir' must be specified."
                )
            kb = SweKnowledgeBase(
                ground_data_dir=ground_data_dir,
                linked_data_dir=linked_data_dir,
                lazy_load_nodes=self.config.knowledge_base.lazy_load_nodes,
            )
        self.kb = kb
        self.kb.load()
        self.llm_client = llm_client or MultiModelLLMClient()
        self.service = ExplanationService(
            kb=self.kb,
            llm_client=self.llm_client,
            config=self.config,
        )

    async def run(
        self,
        swe_context: SweContext,
        original_code: str,
        modified_code: str,
        **_: Any,
    ) -> SweCodeChangeExplanation:
        """Asynchronously judge and explain a code change.

        Parameters mirror the MCP tool in Stage 2:
        - ``swe_context``: output from ``build_swe_code_context``.
        - ``original_code``: code before applying the change.
        - ``modified_code``: code after applying the change.
        """

        return self.service.explain_change(
            swe_context=swe_context,
            original_code=original_code,
            modified_code=modified_code,
        )

