import json
import logging
from typing import Any
import os

from ..llm_client.multi_model_llm_client import MultiModelLLMClient


class ReliabilityDesignTool:
    """
    Tool for analyzing and generating reliability design code.
    Workflow:
    1. Extract input from natural language using extract_reliability_input.md
    2. Identify design using identify_reliability_design.md
    3. Use a strategy selector to execute the template under templates/reliability
    4. Output new code
    """

    def __init__(self, **kwargs: Any):
        self.extract_prompt_path = os.path.join(
            "templates", "utils", "extract_reliability_input.md"
        )
        self.identify_prompt_path = os.path.join(
            "templates", "reliability", "utils", "identify_reliability_design.md"
        )
        self.add_design_pattern_template = os.path.join(
            "templates", "reliability", "base_template.md"
        )
        self.tests_template = os.path.join(
            "templates", "reliability", "test_base_template.md"
        )
        self.llm_client = kwargs.get("llm_client") or MultiModelLLMClient()

    @staticmethod
    def get_raw_response(llm_response: Any) -> str:
        """Normalize an LLM response into a plain string.

        The LocalAI client already returns a string, but this helper keeps the
        tool robust if a future client returns a richer object.
        """

        if isinstance(llm_response, str):
            return llm_response
        return str(llm_response)

    def read_templates(self):
        with open(self.add_design_pattern_template, "r", encoding="utf-8") as f:
            self.add_design_pattern_template_content = f.read()

        with open(self.tests_template, "r", encoding="utf-8") as f:
            self.tests_template_content = f.read()

    def extract_input(self, input: str, models=None):
        # Use LLM to extract input from natural language
        logging.debug(
            "Extracting input using LLM and extract_reliability_input.md prompt..."
        )
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
        return self.get_raw_response(llm_response)

    def select_and_execute_template(self, design_pattern, models=None):
        # Strategy selector for template execution
        logging.debug(f"Selecting template for: {design_pattern}")
        template_dir = os.path.join(
            "templates", "reliability", design_pattern.lower().replace(" ", "_")
        )
        base_template_path = os.path.join(template_dir, "base_design.json")

        # Ensure the base and test templates are loaded into memory.
        if not hasattr(self, "add_design_pattern_template_content"):
            self.read_templates()

        if os.path.exists(base_template_path):
            logging.debug(f"Executing template: {base_template_path}")
            with open(base_template_path, "r", encoding="utf-8") as f:
                template_content = f.read()

            variables = json.loads(template_content)
            new_prompt = self.add_design_pattern_template_content
            for key, value in variables.items():
                new_prompt = new_prompt.replace(f"{{{{{key}}}}}", value)

            llm_response = (
                self.llm_client.chat(new_prompt, model=models)
                if models
                else self.llm_client.chat(new_prompt)
            )
            # Simulate code generation using template
            new_code = self.get_raw_response(llm_response)
        else:
            # No pattern-specific JSON template was found. Fall back to the
            # generic reliability base template and log a warning so users
            # understand why a default path was taken.
            logging.warning(
                "No reliability template found for design pattern '%s'; "
                "falling back to the default base template.",
                design_pattern,
            )

            # Minimal substitution allowing templates to reference the
            # pattern name via {{design_pattern_name}}.
            new_prompt = self.add_design_pattern_template_content.replace(
                "{{design_pattern_name}}", str(design_pattern)
            )

            llm_response = (
                self.llm_client.chat(new_prompt, model=models)
                if models
                else self.llm_client.chat(new_prompt)
            )
            new_code = self.get_raw_response(llm_response)
        return new_code

    async def run(
        self,
        messages: str | list[str] | None = None,
        **kwargs: Any,
    ) -> str:
        # For now, assume messages is a single prompt string
        if isinstance(messages, list):
            raw_message = "\n".join(str(m) for m in messages)
        else:
            raw_message = str(messages) if messages is not None else ""

        extracted = self.extract_input(raw_message)

        # The LLM is expected to return a structure that includes
        # a selected design pattern name and formatted pattern name.
        # We keep the existing contract but delegate to the LLM output.
        selected_design_pattern = extracted.get("selected_design_pattern")
        if selected_design_pattern is None:
            # Fall back to using the raw LLM response if the
            # higher-level fields are not present.
            selected_design_pattern = extracted.get("llm_response", "")

        design_info = self.identify_design(selected_design_pattern)
        formatted_design_pattern_name = (
            design_info["formatted_design_pattern_name"]
            if isinstance(design_info, dict)
            else design_info
        )

        new_code = self.select_and_execute_template(formatted_design_pattern_name)
        return new_code
