from __future__ import annotations

import logging
from typing import List

from src.models.code_gen_plan import CodeGenPlan
from src.models.swe_context import SweContext
from src.service.prompt_asset_writer_service import PromptAssetWriterService
from src.service.prompt_template_execution_service import PromptTemplateExecutionService

# Keep historical logger name for smoke-test log capture compatibility.
LOGGER = logging.getLogger("src.mcp.tools.swe_mcp_tools")
_PROMPT_TEMPLATE_SERVICE = PromptTemplateExecutionService(logger=LOGGER)
_PROMPT_ASSET_WRITER = PromptAssetWriterService()


class BuildSweCodeContextTool:
    """Class-based build-context tool for easier mocking and unit testing."""

    def __init__(self, registry) -> None:
        self._registry = registry

    def execute(
        self,
        plan: CodeGenPlan,
        include_templates: bool = True,
        security_extra_context: str | None = None,
        prompt_output_folder: str | None = None,
        write_executed_prompts: bool = False,
    ) -> SweContext:
        """Build SWE/NFR injection context for a planned code change."""

        ctx = self._registry._create_swe_server_context()
        kb = ctx.kb

        nfr_ids = kb.find_nfr_ids(plan.nfr_focus) if plan.nfr_focus else []
        summary = kb.summarize_for_prompt(nfr_ids)
        LOGGER.info(
            "Building SWE code context for problem '%s' (nfr_ids=%d, include_templates=%s)",
            plan.problem_description,
            len(nfr_ids),
            include_templates,
        )

        templates: List[dict] = []
        if include_templates:
            templates = ctx.templates
            LOGGER.info(
                "Loaded %d concern template/data assets into context", len(templates)
            )

        if prompt_output_folder:
            try:
                executed_prompts: list[dict] | None = None
                if write_executed_prompts:
                    executed_prompts = _PROMPT_TEMPLATE_SERVICE.build_executed_prompts(
                        templates
                    )

                prompt_context = _PROMPT_TEMPLATE_SERVICE.render_prompt_context(
                    swe_summary=summary,
                    templates=templates,
                    security_extra_context=security_extra_context,
                )

                output_path = _PROMPT_ASSET_WRITER.persist_generated_prompt_assets(
                    repo_root=ctx.repo_root,
                    output_folder=prompt_output_folder,
                    plan=plan,
                    swe_summary=summary,
                    templates=templates,
                    security_extra_context=security_extra_context,
                    prompt_context=prompt_context,
                    executed_prompts=executed_prompts,
                )
                LOGGER.info("Generated prompt artifacts written to %s", output_path)
            except OSError as exc:
                LOGGER.warning(
                    "Could not persist generated prompt artifacts to '%s': %s",
                    prompt_output_folder,
                    exc,
                )

        return SweContext(
            plan=plan,
            swe_summary=summary,
            templates=templates,
            security_context=security_extra_context,
        )
