import os
import glob
import pytest
from agent_framework import ChatAgent
from llm_client.multi_model_llm_client import MultiModelLLMClient
from tools.reliability_design import ReliabilityDesignTool
from evaluation.reliability_evaluation import ReliabilityEvaluationTool

# Collect all design pattern folders under templates/reliability
TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "../templates/reliability")
pattern_dirs = [
    d for d in glob.glob(os.path.join(TEMPLATES_DIR, "*")) if os.path.isdir(d)
]

test_cases = []
for pattern_dir in pattern_dirs:
    pattern_name = os.path.basename(pattern_dir)
    # Look for reference code in tests/reference_code/{pattern_name}.cs or .py
    reference_dir = os.path.join(os.path.dirname(__file__), "reference_code")
    reference_code = None
    for ext in [".cs", ".py", ".txt"]:
        ref_file = os.path.join(reference_dir, f"{pattern_name}{ext}")
        if os.path.exists(ref_file):
            with open(ref_file, "r", encoding="utf-8") as f:
                reference_code = f.read()
            break
    # Look for code example in tests/examples/{pattern_name}.cs or .py
    examples_dir = os.path.join(os.path.dirname(__file__), "examples")
    code_example = None
    for ext in [".cs", ".py", ".txt"]:
        example_file = os.path.join(examples_dir, f"{pattern_name}{ext}")
        if os.path.exists(example_file):
            with open(example_file, "r", encoding="utf-8") as f:
                code_example = f.read()
            break
    if code_example and reference_code:
        test_cases.append((pattern_name, code_example, reference_code))


@pytest.mark.asyncio
@pytest.mark.parametrize("pattern_name, code_example, reference_code", test_cases)
async def test_add_reliability_pattern(pattern_name, code_example, reference_code):
    llm_client = MultiModelLLMClient()
    reliability_tool = ReliabilityDesignTool(llm_client=llm_client)
    prompt = f"Add a {pattern_name.replace('_', ' ')} design pattern to the following code:\n{code_example}"
    response = await reliability_tool.run(prompt)
    # Normalize agent response (strip, unify line endings)
    evaluator = ReliabilityEvaluationTool()
    normalized_response = evaluator.extract_code_from_agent_response(response)
    print(f"Agent response for {pattern_name}:\n", normalized_response)
    # Evaluate agent response against reference code

    scores = evaluator.evaluate(
        generated_code=normalized_response, reference_code=reference_code
    )
    print(f"Reliability Evaluation Scores for {pattern_name}:", scores)
