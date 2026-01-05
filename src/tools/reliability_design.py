import json
import logging
from typing import Any
from agent_framework import AgentRunResponse, AgentThread, BaseAgent, ChatMessage, ToolProtocol
from ..llm_client.multi_model_llm_client import MultiModelLLMClient
import os


class ReliabilityDesignTool(BaseAgent):
    """
    Tool for analyzing and generating reliability design code.
    Workflow:
    1. Extract input from natural language using extract_reliability_input.md
    2. Identify design using identify_reliability_design.md
    3. Use a strategy selector to execute the template under templates/reliability
    4. Output new code
    """

    def __init__(self, **kwargs: Any):
        super().__init__(
            name="ReliabilityDesignTool",
            description="Tool for designing and generating reliability design patterns in code.",
            **kwargs,
        )
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
        self.llm_client = kwargs['llm_client'] or MultiModelLLMClient()

    def read_templates(self):
        with open(self.add_design_pattern_template, "r", encoding="utf-8") as f:
            self.add_design_pattern_template_content = f.read()
        
        with open(self.tests_template, "r", encoding="utf-8") as f:
            self.tests_template_content = f.read()

    def extract_input(self, input: str, models=None):
        # Use LLM to extract input from natural language
        logging.debug("Extracting input using LLM and extract_reliability_input.md prompt...")
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
            new_code = f"// No template found for {design_pattern}"
        return new_code

    async def run(
        self,
        messages: str | ChatMessage | list[str] | list[ChatMessage] | None = None,
        *,
        thread: AgentThread | None = None,
        **kwargs: Any,
    ) -> AgentRunResponse:
        raw_message = self.get_raw_response(messages) if isinstance(messages, ChatMessage) else messages
        extracted = self.extract_input(raw_message)
        design_info = self.identify_design(extracted["selected_design_pattern"])
        new_code = self.select_and_execute_template(
            design_info["formatted_design_pattern_name"]
        )

        return AgentRunResponse(messages=new_code)
    
    def get_raw_response(self, message: ChatMessage) -> str:
        response = ""
        for m in message.contents:
            response += m.text
        return response