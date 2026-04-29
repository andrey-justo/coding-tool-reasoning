from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

from src.service.prompt_data_mapping_service import PromptDataMappingService


class PromptTemplateExecutionService:
    """Build prompt context and render executable prompt templates."""

    def __init__(
        self,
        logger,
        data_mapping_service: Optional[PromptDataMappingService] = None,
        placeholder_pattern: Optional[re.Pattern[str]] = None,
    ) -> None:
        self._logger = logger
        self._data_mapping_service = data_mapping_service or PromptDataMappingService()
        self._placeholder_pattern = placeholder_pattern or re.compile(
            r"\{\{\s*([A-Za-z0-9_.-]+)\s*\}\}"
        )

    def render_prompt_context(
        self,
        swe_summary: str,
        templates: List[dict],
        security_extra_context: Optional[str],
    ) -> str:
        sections: List[str] = ["# SWE Prompt Context", "", "## SWE Summary", swe_summary]

        if security_extra_context:
            sections.extend(["", "## Security Extra Context", security_extra_context])

        if templates:
            sections.append("")
            sections.append("## Concern Templates")
            for template in templates:
                title = template.get("name") or template.get("concern_group") or "template"
                sections.extend(["", f"### {title}", str(template.get("content", ""))])

        return "\n".join(sections).strip() + "\n"

    def build_executed_prompts(self, templates: List[dict]) -> List[dict]:
        data_map = self._data_mapping_service.extract_prompt_data_map(templates)
        executed: List[dict] = []
        has_code_example = bool(data_map.get("CODE_EXAMPLE", "").strip())
        has_unit_test_example = bool(data_map.get("UNIT_TEST_EXAMPLE", "").strip())

        for item in templates:
            if item.get("kind") != "swe_concern_template":
                continue

            template_name = str(item.get("name") or item.get("concern_group") or "template")
            if template_name == "test_base_template" and not has_unit_test_example:
                self._logger.info(
                    "Skipping prompt template '%s' because no unit test example data was found",
                    template_name,
                )
                continue

            template_content = str(item.get("content", ""))
            rendered, missing = self._render_template_content(template_content, data_map)
            if missing:
                self._logger.info(
                    "Skipping prompt template '%s' due to missing placeholders: %s",
                    template_name,
                    ", ".join(missing),
                )
                continue

            rendered = self._apply_optional_markdown_rules(
                template_name=template_name,
                rendered=rendered,
                has_code_example=has_code_example,
                has_unit_test_example=has_unit_test_example,
            )

            executed.append(
                {
                    "name": template_name,
                    "content": rendered,
                }
            )

        return executed

    def _render_template_content(
        self,
        content: str,
        data_map: Dict[str, str],
    ) -> Tuple[str, List[str]]:
        placeholders = self._placeholder_pattern.findall(content)
        if not placeholders:
            return self._replace_single_brace_example_placeholders(content, data_map), []

        missing = [name for name in placeholders if name not in data_map]
        if missing:
            return content, missing

        rendered = content
        for name in placeholders:
            rendered = re.sub(
                rf"\{{\{{\s*{re.escape(name)}\s*\}}\}}",
                data_map[name],
                rendered,
            )

        # Some legacy templates use single-brace placeholders for examples.
        rendered = self._replace_single_brace_example_placeholders(rendered, data_map)

        return rendered, []

    @staticmethod
    def _replace_single_brace_example_placeholders(
        content: str,
        data_map: Dict[str, str],
    ) -> str:
        replacements = {
            "{CODE EXAMPLE}": data_map.get("CODE_EXAMPLE", ""),
            "{CODE_EXAMPLE}": data_map.get("CODE_EXAMPLE", ""),
            "{UNIT_TEST_EXAMPLE}": data_map.get("UNIT_TEST_EXAMPLE", ""),
            "{UNIT TEST EXAMPLE}": data_map.get("UNIT_TEST_EXAMPLE", ""),
            "{Example Description}": data_map.get("EXAMPLE_DESCRIPTION", ""),
            "{Design Pattern Name}": data_map.get("DESIGN_PATTERN_NAME", ""),
        }

        rendered = content
        for token, value in replacements.items():
            if value:
                rendered = rendered.replace(token, value)
        return rendered

    def _apply_optional_markdown_rules(
        self,
        template_name: str,
        rendered: str,
        has_code_example: bool,
        has_unit_test_example: bool,
    ) -> str:
        content = rendered
        if not has_code_example:
            content = self._remove_example_section(content)
        if not has_unit_test_example:
            content = self._remove_unit_tests_section(content)
            if template_name == "test_base_template":
                content = self._remove_example_section(content)
        return content

    @staticmethod
    def _remove_example_section(content: str) -> str:
        pattern = re.compile(
            r"\n##{1,2}\s+Example\s+1:.*?(?=\n##\s+|\Z)",
            flags=re.DOTALL,
        )
        return pattern.sub("", content)

    @staticmethod
    def _remove_unit_tests_section(content: str) -> str:
        return re.sub(
            r"\n##\s+Unit Tests:.*?(\n|\Z)",
            "\n",
            content,
        )
