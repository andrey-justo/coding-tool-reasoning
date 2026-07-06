from __future__ import annotations

import logging
from typing import Any, Callable, List, Optional, Type

from src.mcp.tools.apply_plan_swe_code_change_tool import ApplyPlanSweCodeChangeTool
from src.mcp.tools.build_swe_code_context_tool import BuildSweCodeContextTool
from src.mcp.tools.find_best_issue_candidates_tool import FindBestIssueCandidatesTool
from src.mcp.tools.judge_swe_code_change_tool import JudgeSweCodeChangeTool
from src.mcp.tools.plan_swe_code_change_tool import PlanSweCodeChangeTool
from src.models.code_gen_plan import CodeGenPlan
from src.models.issue_candidate_ranking import (
    IssueCandidate,
    IssueCandidateRankingResult,
    PullRequestContext,
)
from src.models.swe_context import SweContext
from src.models.swe_explanation import SweCodeChangeExplanation

LOGGER = logging.getLogger(__name__)


class SweMcpToolRegistry:
    """Class-based implementation of SWE MCP tools for easier unit testing."""

    def __init__(
        self,
        create_swe_server_context: Callable[..., Any],
        planner_cls: Optional[Type[Any]] = None,
        explanation_service_cls: Optional[Type[Any]] = None,
        issue_candidate_ranking_service_cls: Optional[Type[Any]] = None,
        llm_client_cls: Optional[Type[Any]] = None,
    ) -> None:
        self._create_swe_server_context = create_swe_server_context
        self._planner_cls = planner_cls
        self._explanation_service_cls = explanation_service_cls
        self._issue_candidate_ranking_service_cls = issue_candidate_ranking_service_cls
        self._llm_client_cls = llm_client_cls
        self._logger = LOGGER
        self._plan_tool = PlanSweCodeChangeTool(self)
        self._build_context_tool = BuildSweCodeContextTool(self)
        self._apply_plan_tool = ApplyPlanSweCodeChangeTool(self)
        self._judge_tool = JudgeSweCodeChangeTool(self)
        self._find_best_issue_candidates_tool = FindBestIssueCandidatesTool(self)

    def apply_plan_swe_code_change(
        self,
        swe_context: SweContext,
        original_code: str,
        target_file: Optional[str] = None,
        temperature: Optional[float] = None,
        seed: Optional[int] = None,
    ) -> dict[str, Any]:
        return self._apply_plan_tool.execute(
            swe_context=swe_context,
            original_code=original_code,
            target_file=target_file,
            temperature=temperature,
            seed=seed,
        )

    def plan_swe_code_change(
        self,
        problem_description: str,
        target_language: Optional[str] = None,
        nfr_focus: Optional[List[str]] = None,
        user_prompt_data: Optional[str] = None,
    ) -> CodeGenPlan:
        return self._plan_tool.execute(
            problem_description=problem_description,
            target_language=target_language,
            nfr_focus=nfr_focus,
            user_prompt_data=user_prompt_data,
        )

    def build_swe_code_context(
        self,
        plan: CodeGenPlan,
        include_templates: bool = True,
        security_extra_context: Optional[str] = None,
        prompt_output_folder: Optional[str] = None,
        write_executed_prompts: bool = False,
    ) -> SweContext:
        return self._build_context_tool.execute(
            plan=plan,
            include_templates=include_templates,
            security_extra_context=security_extra_context,
            prompt_output_folder=prompt_output_folder,
            write_executed_prompts=write_executed_prompts,
        )

    def judge_swe_code_change(
        self,
        swe_context: SweContext,
        original_code: str,
        modified_code: str,
    ) -> SweCodeChangeExplanation:
        return self._judge_tool.execute(
            swe_context=swe_context,
            original_code=original_code,
            modified_code=modified_code,
        )

    def find_best_issue_candidates_for_current_pr(
        self,
        current_pr: PullRequestContext,
        issue_candidates: List[IssueCandidate],
        top_k: int = 5,
        min_score: float = 0.15,
        target_language: Optional[str] = None,
        nfr_focus: Optional[List[str]] = None,
    ) -> IssueCandidateRankingResult:
        return self._find_best_issue_candidates_tool.execute(
            current_pr=current_pr,
            issue_candidates=issue_candidates,
            top_k=top_k,
            min_score=min_score,
            target_language=target_language,
            nfr_focus=nfr_focus,
        )

    def register_on_mcp(self, mcp: Any) -> None:
        """Register class-backed methods as MCP tools."""

        @mcp.tool()
        def plan_swe_code_change(
            problem_description: str,
            target_language: Optional[str] = None,
            nfr_focus: Optional[List[str]] = None,
            user_prompt_data: Optional[str] = None,
        ) -> CodeGenPlan:
            return self.plan_swe_code_change(
                problem_description=problem_description,
                target_language=target_language,
                nfr_focus=nfr_focus,
                user_prompt_data=user_prompt_data,
            )

        @mcp.tool()
        def build_swe_code_context(
            plan: CodeGenPlan,
            include_templates: bool = True,
            security_extra_context: Optional[str] = None,
            prompt_output_folder: Optional[str] = None,
            write_executed_prompts: bool = False,
        ) -> SweContext:
            return self.build_swe_code_context(
                plan=plan,
                include_templates=include_templates,
                security_extra_context=security_extra_context,
                prompt_output_folder=prompt_output_folder,
                write_executed_prompts=write_executed_prompts,
            )

        @mcp.tool()
        def apply_plan_swe_code_change(
            swe_context: SweContext,
            original_code: str,
            target_file: Optional[str] = None,
            temperature: Optional[float] = None,
            seed: Optional[int] = None,
        ) -> dict[str, Any]:
            return self.apply_plan_swe_code_change(
                swe_context=swe_context,
                original_code=original_code,
                target_file=target_file,
                temperature=temperature,
                seed=seed,
            )

        @mcp.tool()
        def judge_swe_code_change(
            swe_context: SweContext,
            original_code: str,
            modified_code: str,
        ) -> SweCodeChangeExplanation:
            return self.judge_swe_code_change(
                swe_context=swe_context,
                original_code=original_code,
                modified_code=modified_code,
            )

        @mcp.tool()
        def find_best_issue_candidates_for_current_pr(
            current_pr: PullRequestContext,
            issue_candidates: List[IssueCandidate],
            top_k: int = 5,
            min_score: float = 0.15,
            target_language: Optional[str] = None,
            nfr_focus: Optional[List[str]] = None,
        ) -> IssueCandidateRankingResult:
            return self.find_best_issue_candidates_for_current_pr(
                current_pr=current_pr,
                issue_candidates=issue_candidates,
                top_k=top_k,
                min_score=min_score,
                target_language=target_language,
                nfr_focus=nfr_focus,
            )


class SweMcpToolsRegistrar:
    """Class-based MCP registration entry point for SWE tools."""

    def __init__(
        self,
        mcp: Any,
        create_swe_server_context: Callable[..., Any],
        planner_cls: Optional[Type[Any]] = None,
        explanation_service_cls: Optional[Type[Any]] = None,
        issue_candidate_ranking_service_cls: Optional[Type[Any]] = None,
        llm_client_cls: Optional[Type[Any]] = None,
    ) -> None:
        self._mcp = mcp
        self._registry = SweMcpToolRegistry(
            create_swe_server_context=create_swe_server_context,
            planner_cls=planner_cls,
            explanation_service_cls=explanation_service_cls,
            issue_candidate_ranking_service_cls=issue_candidate_ranking_service_cls,
            llm_client_cls=llm_client_cls,
        )

    def register(self) -> None:
        """Register all SWE MCP tools on the configured MCP instance."""

        self._registry.register_on_mcp(self._mcp)


def register_swe_mcp_tools(
    mcp: Any, create_swe_server_context: Callable[..., Any]
) -> None:
    """Backwards-compatible function wrapper for MCP tool registration."""

    SweMcpToolsRegistrar(
        mcp=mcp,
        create_swe_server_context=create_swe_server_context,
    ).register()
