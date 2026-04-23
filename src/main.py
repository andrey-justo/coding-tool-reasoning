"""Simple CLI entry point for the migration helper app.

Previously this used agent_framework's dev UI; it now exposes a
minimal command-line interface around ReliabilityDesignTool.
"""

import asyncio

from llm_client.multi_model_llm_client import MultiModelLLMClient
from tools.reliability_design import ReliabilityDesignTool


async def main() -> None:
    llm_client = MultiModelLLMClient()
    reliability_tool = ReliabilityDesignTool(llm_client=llm_client)

    prompt = input("Enter a reliability design request: ")
    result = await reliability_tool.run(prompt)
    print("\nGenerated code:\n")
    print(result)


if __name__ == "__main__":
    asyncio.run(main())
