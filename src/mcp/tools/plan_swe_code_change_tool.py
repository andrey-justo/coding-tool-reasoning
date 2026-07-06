from __future__ import annotations

from src.models.code_gen_plan import CodeGenPlan
from src.service.intent_planner import IntentPlanner


class PlanSweCodeChangeTool:
    """Class-based plan tool for easier mocking and unit testing."""

    def __init__(self, registry) -> None:
        self._registry = registry

    def execute(
        self,
        problem_description: str,
        target_language: str | None = None,
        nfr_focus: list[str] | None = None,
        user_prompt_data: str | None = None,
    ) -> CodeGenPlan:
        """Create a high-level plan for a code change before generation."""

        ctx = self._registry._create_swe_server_context()
        kb = ctx.kb

        planner_cls = self._registry._planner_cls or IntentPlanner
        planner = planner_cls(kb=kb, config=ctx.config)
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
            llm_prompt=getattr(planning_result, "llm_prompt", None),
            llm_raw_response=getattr(planning_result, "llm_raw_response", None),
        )
