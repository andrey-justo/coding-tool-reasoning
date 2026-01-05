from typing import Any
from agent_framework import AgentRunResponse, AgentThread, BaseAgent, ChatMessage
from ..llm_client.multi_model_llm_client import MultiModelLLMClient


class JudgeCodeChangesStep(BaseAgent):
    def __init__(self, llm_client=None):
        super().__init__()
        self.llm_client = llm_client or MultiModelLLMClient()

    async def run(
        self,
        messages: str | ChatMessage | list[str] | list[ChatMessage] | None = None,
        *,
        thread: AgentThread | None = None,
        **kwargs: Any,
    ) -> AgentRunResponse:
        return AgentRunResponse(messages="")