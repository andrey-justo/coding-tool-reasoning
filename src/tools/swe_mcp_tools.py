from typing import Any, Callable, List, Optional

from business_logic.explanation_service import ExplanationService
from business_logic.intent_planner import IntentPlanner
from models.code_gen_plan import CodeGenPlan
from models.swe_context import SweContext
from models.swe_explanation import SweCodeChangeExplanation


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
        )

        return CodeGenPlan(
            problem_description=problem_description,
            target_language=target_language,
            nfr_focus=planning_result.nfr_focus,
            high_level_steps=planning_result.high_level_steps,
            related_entities=planning_result.resolved_nfr_ids,
        )

    @mcp.tool()
    def build_swe_code_context(
        plan: CodeGenPlan,
        include_templates: bool = True,
        security_extra_context: Optional[str] = None,
    ) -> SweContext:
        """Build SWE/NFR injection context for a planned code change.

        Call this *after* `plan_swe_code_change`. It:
        - Resolves NFRs and related entities from ground_data and linked_data
        - Produces a compact text block you can prepend to your code generation prompt
        - Optionally includes reliability design templates for additional requirements
        """

        ctx = create_swe_server_context()
        kb = ctx.kb

        nfr_ids = kb.find_nfr_ids(plan.nfr_focus) if plan.nfr_focus else []
        summary = kb.summarize_for_prompt(nfr_ids)

        templates: List[dict] = []
        if include_templates:
            templates = ctx.templates

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
