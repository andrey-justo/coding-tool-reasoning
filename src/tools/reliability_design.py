from agent_framework import ToolProtocol
from llm_client.multi_model_llm_client import MultiModelLLMClient
import os


class ReliabilityDesignTool(ToolProtocol):
    """
    Tool for analyzing and generating reliability design code.
    Workflow:
    1. Extract input from natural language using extract_reliability_input.md
    2. Identify design using identify_reliability_design.md
    3. Use a strategy selector to execute the template under templates/reliability
    4. Output new code
    """

    def __init__(self, llm_client=None):
        self.name = "ReliabilityDesignTool"
        self.description = (
            "Tool for designing and generating reliability design patterns in code."
        )
        self.extract_prompt_path = os.path.join(
            "templates", "utils", "extract_reliability_input.md"
        )
        self.identify_prompt_path = os.path.join(
            "templates", "reliability", "utils", "identify_reliability_design.md"
        )
        self.llm_client = llm_client or MultiModelLLMClient()

    def extract_input(self, input: str, models=None):
        # Use LLM to extract input from natural language
        print("Extracting input using LLM and extract_reliability_input.md prompt...")
        with open(self.extract_prompt_path, "r", encoding="utf-8") as f:
            prompt_template = f.read()
        prompt = prompt_template.replace("{{input}}", input)
        llm_response = (
            self.llm_client.chat(prompt, model=models)
            if models
            else self.llm_client.chat(prompt)
        )
        # For demonstration, just return the LLM response as a string in a dict
        return {"llm_response": llm_response}

    def identify_design(self, original_name, models=None):
        # Use LLM to identify design
        print(
            "Identifying design using LLM and identify_reliability_design.md prompt..."
        )
        with open(self.identify_prompt_path, "r", encoding="utf-8") as f:
            prompt_template = f.read()
        prompt = prompt_template.replace("{{input}}", original_name)
        llm_response = (
            self.llm_client.chat(prompt, model=models)
            if models
            else self.llm_client.chat(prompt)
        )
        return {"llm_response": llm_response}

    def select_and_execute_template(self, design_pattern):
        # Strategy selector for template execution
        print(f"Selecting template for: {design_pattern}")
        template_dir = os.path.join(
            "templates", "reliability", design_pattern.lower().replace(" ", "_")
        )
        base_template_path = os.path.join(template_dir, "base_design.json")
        if os.path.exists(base_template_path):
            print(f"Executing template: {base_template_path}")
            with open(base_template_path, "r", encoding="utf-8") as f:
                template_content = f.read()
            # Simulate code generation using template
            new_code = f"// Generated code for {design_pattern}\n{template_content}"
        else:
            new_code = f"// No template found for {design_pattern}"
        return new_code

    def protocol(self, input: str) -> ToolProtocol:
        extracted = self.extract_input(input)
        design_info = self.identify_design(extracted["selected_design_pattern"])
        new_code = self.select_and_execute_template(
            design_info["formatted_design_pattern_name"]
        )
        print("\n--- Output New Code ---")
        print(new_code)
