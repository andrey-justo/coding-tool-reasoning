from agent_framework import ChatAgent
from agent_framework.openai import OpenAIChatClient
from agent_framework.devui import serve

"""
Main entry point for the migration helper app.
"""

from llm_client.multi_model_llm_client import MultiModelLLMClient
from tools.reliability_design import ReliabilityDesignTool

if __name__ == "__main__":
    llm_client = MultiModelLLMClient()
    reliability_tool = ReliabilityDesignTool(llm_client=llm_client)
    agent = ChatAgent(
        name="Reliability Design Agent",
        chat_client=llm_client.openai_client(),
        tools=[reliability_tool],
    )

# Launch debug UI - that's it!
serve(entities=[agent], auto_open=True)
# → Opens browser to http://localhost:8080
