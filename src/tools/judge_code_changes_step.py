from typing import Any, Optional

from ..business_logic.explanation_service import ExplanationService
from ..business_logic.swe_taxonomy_service import SweKnowledgeBase
from ..llm_client.multi_model_llm_client import MultiModelLLMClient
from ..models.swe_config import SweMcpConfig
from ..models.swe_context import SweContext
from ..models.swe_explanation import SweCodeChangeExplanation


class JudgeCodeChangesStep:
    """Judge & explain code changes using the SWE taxonomy and an LLM.

    This class is a lightweight wrapper around :class:`ExplanationService`
    so it can be plugged into higher-level workflows or agents. It does
    not depend on agent_framework and can be called directly.
    """

    def __init__(
        self,
        kb: Optional[SweKnowledgeBase] = None,
        llm_client: Optional[MultiModelLLMClient] = None,
        config: Optional[SweMcpConfig] = None,
    ) -> None:
        self.kb = kb or SweKnowledgeBase()
        self.kb.load()
        self.llm_client = llm_client or MultiModelLLMClient()
        self.config = config or SweMcpConfig()
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
