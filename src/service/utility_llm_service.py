from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from src.llm_client.multi_model_llm_client import MultiModelLLMClient
from src.service.tool_prompt_template_service import ToolPromptTemplateService

logger = logging.getLogger(__name__)
Result = TypeVar("Result", bound=BaseModel)
MAX_RESPONSE_CORRECTIONS = 1


class UtilityLlmService:
    """Run schema-validated semantic decisions using external utility prompts."""

    def __init__(
        self,
        llm_client: MultiModelLLMClient | None = None,
        templates_root: str | Path | None = None,
    ) -> None:
        self._client = llm_client
        self._templates = ToolPromptTemplateService(
            templates_root or Path(__file__).resolve().parents[2] / "templates",
            subdirectory="utils",
        )

    def render(
        self,
        template: str,
        payload: dict[str, Any],
        result_type: type[BaseModel] | None = None,
    ) -> str:
        values = {"INPUT_JSON": json.dumps(payload, ensure_ascii=False)}
        if result_type is not None:
            values["SCHEMA"] = json.dumps(result_type.model_json_schema())
        return self._templates.render(template, values)

    def complete(
        self,
        template: str,
        result_type: type[Result],
        payload: dict[str, Any],
    ) -> Result:
        try:
            original_prompt = self.render(template, payload, result_type)
            prompt = original_prompt
            if self._client is None:
                self._client = MultiModelLLMClient()
            corrections = 0
            while True:
                response = self._client.chat(prompt)
                try:
                    return result_type.model_validate_json(response)
                except ValidationError as error:
                    if corrections >= MAX_RESPONSE_CORRECTIONS:
                        raise
                    corrections += 1
                    logger.warning(
                        "LLM utility decision '%s' violated its response contract; "
                        "requesting one model correction (%s/%s): %s",
                        template,
                        corrections,
                        MAX_RESPONSE_CORRECTIONS,
                        error,
                    )
                    prompt = self.render(
                        "structured_response_correction",
                        {
                            "original_request": original_prompt,
                            "previous_response": response,
                            "validation_error": str(error),
                        },
                        result_type,
                    )
        except Exception:
            logger.exception(
                "LLM utility decision '%s' failed; no heuristic fallback is permitted",
                template,
            )
            raise
