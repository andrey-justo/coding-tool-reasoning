import asyncio
from agent_framework import ChatAgent
from agent_framework.devui import serve

"""
Main entry point for the migration helper app.
"""

from llm_client.multi_model_llm_client import MultiModelLLMClient
from tools.reliability_design import ReliabilityDesignTool


def main():
    llm_client = MultiModelLLMClient()
    reliability_tool_agent = ReliabilityDesignTool(llm_client=llm_client)

    # Launch debug UI - that's it!
    serve(entities=[reliability_tool_agent], auto_open=True)
    # → Opens browser to http://localhost:8080


if __name__ == "__main__":
    asyncio.run(main())
