from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime
from typing import Any, Callable, List, Optional

from src.business_logic.explanation_service import ExplanationService
from src.business_logic.intent_planner import IntentPlanner
from src.models.code_gen_plan import CodeGenPlan
from src.models.swe_context import SweContext
from src.models.swe_explanation import SweCodeChangeExplanation


LOGGER = logging.getLogger(__name__)


def _slugify_for_filename(text: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-").lower()
    if not slug:
        return "prompt"
    return slug[:48]


def _render_prompt_context(
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


def _persist_generated_prompt_assets(
    repo_root: str,
    output_folder: str,
    plan: CodeGenPlan,
    swe_summary: str,
    templates: List[dict],
    security_extra_context: Optional[str],
) -> str:
    resolved_output_root = (
        output_folder
        if os.path.isabs(output_folder)
        else os.path.join(repo_root, output_folder)
    )
    run_id = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    run_folder = os.path.join(
        resolved_output_root,
        f"{run_id}-{_slugify_for_filename(plan.problem_description)}",
    )
    os.makedirs(run_folder, exist_ok=True)

    plan_payload = plan.model_dump()
    with open(os.path.join(run_folder, "plan.json"), "w", encoding="utf-8") as f:
        json.dump(plan_payload, f, ensure_ascii=False, indent=2)

    with open(os.path.join(run_folder, "swe_summary.md"), "w", encoding="utf-8") as f:
        f.write(swe_summary)

    prompt_context = _render_prompt_context(
        swe_summary=swe_summary,
        templates=templates,
        security_extra_context=security_extra_context,
    )
    with open(os.path.join(run_folder, "prompt_context.md"), "w", encoding="utf-8") as f:
        f.write(prompt_context)

    if templates:
        templates_folder = os.path.join(run_folder, "templates")
        os.makedirs(templates_folder, exist_ok=True)
        for index, template in enumerate(templates, start=1):
            template_name = template.get("name") or template.get("concern_group") or f"template-{index}"
            template_file = f"{index:02d}-{_slugify_for_filename(str(template_name))}.md"
            template_content = str(template.get("content", ""))
            with open(
                os.path.join(templates_folder, template_file),
                "w",
                encoding="utf-8",
            ) as f:
                f.write(template_content)

    return run_folder


def register_swe_mcp_tools(
    mcp: Any, create_swe_server_context: Callable[..., Any]
) -> None:
    """Register SWE-related MCP tools on the given FastMCP instance.

    This keeps the actual MCP tools under the tools package while allowing the
    server module to own the MCP instance and server context factory.
    """

    @mcp.tool()
    def plan_swe_code_change(
        problem_description: str,
        target_language: Optional[str] = None,
        nfr_focus: Optional[List[str]] = None,
        user_prompt_data: Optional[str] = None,
    ) -> CodeGenPlan:
        """Create a high-level plan for a code change before generation.

        This tool should be called *first* by the agent. It analyzes the
        requested change and NFR focus and returns a structured plan. Call
        `build_swe_code_context` next to get prompt-ready injection text and
        templates for the actual code generation.
        """

        ctx = create_swe_server_context()
        kb = ctx.kb

        # Stage 1: taxonomy-guided planning via IntentPlanner.
        planner = IntentPlanner(kb=kb, config=ctx.config)
        planning_result = planner.plan(
            problem_description=problem_description,
            target_language=target_language,
            nfr_focus=nfr_focus,
            user_prompt_data=user_prompt_data,
        )

        return CodeGenPlan(
            problem_description=problem_description,
            target_language=planning_result.inferred_target_language,
            nfr_focus=planning_result.nfr_focus,
            high_level_steps=planning_result.high_level_steps,
            related_entities=planning_result.resolved_nfr_ids,
        )

    @mcp.tool()
    def build_swe_code_context(
        plan: CodeGenPlan,
        include_templates: bool = True,
        security_extra_context: Optional[str] = None,
        prompt_output_folder: Optional[str] = None,
    ) -> SweContext:
        """Build SWE/NFR injection context for a planned code change.

        Call this *after* `plan_swe_code_change`. It:
        - Resolves NFRs and related entities from ground_data and linked_data
        - Produces a compact text block you can prepend to your code generation prompt
        - Optionally includes concern templates/data loaded by the server
        - Optionally writes generated prompt artifacts to disk for audit/debug
        """

        ctx = create_swe_server_context()
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
            LOGGER.info("Loaded %d concern template/data assets into context", len(templates))

        if prompt_output_folder:
            try:
                output_path = _persist_generated_prompt_assets(
                    repo_root=ctx.repo_root,
                    output_folder=prompt_output_folder,
                    plan=plan,
                    swe_summary=summary,
                    templates=templates,
                    security_extra_context=security_extra_context,
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

    @mcp.tool()
    def judge_swe_code_change(
        swe_context: SweContext,
        original_code: str,
        modified_code: str,
    ) -> SweCodeChangeExplanation:
        """Stage 2 – judge and explain a code change.

        This tool should be called *after* code has been generated or
        modified using the plan and context from Stage 1/2:

        1. Call ``plan_swe_code_change`` to obtain a :class:`CodeGenPlan`.
        2. Call ``build_swe_code_context`` to construct a :class:`SweContext`.
        3. Apply the planned changes in your own agent / tool chain.
        4. Finally, call this tool with the original and modified code.

        The result is a :class:`SweCodeChangeExplanation` that contains
        an overall verdict, rationale, per-NFR impacts, risks and
        recommended tests, all grounded in the SWE taxonomy rather than
        a separate ontology graph.
        """

        ctx = create_swe_server_context()
        kb = ctx.kb
        service = ExplanationService(kb=kb, config=ctx.config)

        return service.explain_change(
            swe_context=swe_context,
            original_code=original_code,
            modified_code=modified_code,
        )
