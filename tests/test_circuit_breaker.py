import random
from agent_framework import ChatAgent
import pytest
from llm_client.multi_model_llm_client import MultiModelLLMClient
from tools.reliability_design import ReliabilityDesignTool
from evaluation.reliability_evaluation import ReliabilityEvaluationTool


@pytest.mark.asyncio
async def test_add_circuit_breaker():
    # Initialize components
    llm_client = MultiModelLLMClient()
    reliability_tool = ReliabilityDesignTool(llm_client=llm_client)

    # Random C# code sample
    cs_samples = [
        "public class Service { public void Call() { /* ... */ } }",
        "try { var result = client.Get(); } catch(Exception ex) { /* ... */ }",
        "public async Task<string> GetDataAsync() { return await http.GetAsync(url); }",
    ]
    cs_code = random.choice(cs_samples)

    # Ask agent to add circuit breaker design pattern
    prompt = (
        f"Add a circuit breaker design pattern to the following C# code:\n{cs_code}"
    )
    response = await reliability_tool.run(prompt)

    # Evaluate agent response using ReliabilityEvaluationTool
    # Use the real circuit breaker reference code
    with open("tests/reference_code/circuit_breaker.cs", "r", encoding="utf-8") as f:
        reference_code = f.read()
    evaluator = ReliabilityEvaluationTool()
    generated_code = evaluator.extract_code_from_agent_response(response)
    scores = evaluator.evaluate(
        generated_code=generated_code, reference_code=reference_code
    )
    print("Reliability Evaluation Scores:", scores)


if __name__ == "__main__":
    test_add_circuit_breaker()
