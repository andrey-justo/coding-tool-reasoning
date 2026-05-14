from __future__ import annotations

import json
import logging
import re
from typing import Any, Callable, List, Optional, Type

from src.models.code_gen_plan import CodeGenPlan
from src.models.swe_config import SweMcpConfig
from src.models.swe_context import SweContext
from src.models.swe_explanation import SweCodeChangeExplanation
from src.service.explanation_service import ExplanationService
from src.service.intent_planner import IntentPlanner
from src.service.prompt_asset_writer_service import PromptAssetWriterService
from src.service.prompt_template_execution_service import PromptTemplateExecutionService

LOGGER = logging.getLogger(__name__)
_PROMPT_TEMPLATE_SERVICE = PromptTemplateExecutionService(logger=LOGGER)
_PROMPT_ASSET_WRITER = PromptAssetWriterService()


class SweMcpToolRegistry:
    """Class-based implementation of SWE MCP tools for easier unit testing."""

    def __init__(
        self,
        create_swe_server_context: Callable[..., Any],
        planner_cls: Optional[Type[Any]] = None,
        explanation_service_cls: Optional[Type[Any]] = None,
    ) -> None:
        self._create_swe_server_context = create_swe_server_context
        self._planner_cls = planner_cls
        self._explanation_service_cls = explanation_service_cls

    def plan_swe_code_change(
        self,
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

        ctx = self._create_swe_server_context()
        kb = ctx.kb

        # Stage 1: taxonomy-guided planning via IntentPlanner.
        planner_cls = self._planner_cls or IntentPlanner
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
        )

    def build_swe_code_context(
        self,
        plan: CodeGenPlan,
        include_templates: bool = True,
        security_extra_context: Optional[str] = None,
        prompt_output_folder: Optional[str] = None,
        write_executed_prompts: bool = False,
    ) -> SweContext:
        """Build SWE/NFR injection context for a planned code change.

        Call this *after* `plan_swe_code_change`. It:
        - Resolves NFRs and related entities from ground_data and linked_data
        - Produces a compact text block you can prepend to your code generation prompt
        - Optionally includes concern templates/data loaded by the server
        - Optionally writes generated prompt artifacts to disk for audit/debug
        - Optionally writes executed prompt templates (rendered with data.json) in timestamp order
        """

        ctx = self._create_swe_server_context()
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

        config = getattr(ctx, "config", SweMcpConfig())
        related_subjects: List[str] = []
        attached_knowledge: List[dict] = []
        if (
            include_templates
            and config.concern_assets.enable_related_subject_discovery
        ):
            related_subjects, attached_knowledge = self._resolve_related_knowledge(
                plan=plan,
                templates=templates,
                max_subjects=config.concern_assets.max_related_subjects,
            )
            if related_subjects:
                LOGGER.info(
                    "Resolved related subjects for explanation: %s",
                    ", ".join(related_subjects),
                )

        if prompt_output_folder:
            try:
                executed_prompts: Optional[List[dict]] = None
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
            related_subjects=related_subjects,
            attached_knowledge=attached_knowledge,
        )

    def _resolve_related_knowledge(
        self,
        plan: CodeGenPlan,
        templates: List[dict],
        max_subjects: int,
    ) -> tuple[List[str], List[dict]]:
        knowledge_items = [
            item for item in templates if item.get("kind") == "swe_concern_data"
        ]
        if not knowledge_items:
            return [], []

        change_text = " ".join(
            [plan.problem_description or "", *[str(step) for step in plan.high_level_steps]]
        ).lower()
        change_tokens = self._tokenize(change_text)

        scored: List[tuple[int, str, dict, dict]] = []
        by_subject: dict[str, tuple[dict, dict]] = {}
        for item in knowledge_items:
            subject = str(item.get("concern_group") or item.get("name") or "").strip()
            if not subject:
                continue

            payload = self._safe_json_loads(str(item.get("content") or ""))
            by_subject[subject] = (item, payload)

            searchable_parts = [
                subject,
                str(payload.get("name", "")),
                str(payload.get("problem", "")),
                " ".join(str(step) for step in payload.get("steps", []) if step),
            ]
            keyword_hits = 0
            for key in ("purpose_keywords", "keywords", "tags"):
                values = payload.get(key)
                if not isinstance(values, list):
                    continue
                for raw in values:
                    phrase = str(raw).strip().lower()
                    if phrase and phrase in change_text:
                        keyword_hits += 1
                        searchable_parts.append(phrase)

            candidate_tokens = self._tokenize(" ".join(searchable_parts).lower())
            overlap = len(change_tokens.intersection(candidate_tokens))
            score = overlap + (keyword_hits * 3)
            if score > 0:
                scored.append((score, subject, item, payload))

        scored.sort(key=lambda entry: (-entry[0], entry[1]))
        selected_subjects: List[str] = []
        selected_items: List[dict] = []

        for _, subject, item, payload in scored:
            if subject in selected_subjects:
                continue
            selected_subjects.append(subject)
            selected_items.append(item)
            if len(selected_subjects) >= max_subjects:
                break

            related = payload.get("related_subjects")
            if not isinstance(related, list):
                continue
            for raw_related in related:
                related_subject = str(raw_related).strip()
                if not related_subject or related_subject in selected_subjects:
                    continue
                related_match = by_subject.get(related_subject)
                if not related_match:
                    continue
                selected_subjects.append(related_subject)
                selected_items.append(related_match[0])
                if len(selected_subjects) >= max_subjects:
                    break

            if len(selected_subjects) >= max_subjects:
                break

        return selected_subjects, selected_items

    @staticmethod
    def _safe_json_loads(raw: str) -> dict:
        try:
            data = json.loads(raw)
            return data if isinstance(data, dict) else {}
        except json.JSONDecodeError:
            return {}

    @staticmethod
    def _tokenize(value: str) -> set[str]:
        return {
            token
            for token in re.findall(r"[A-Za-z0-9_]+", value)
            if len(token) >= 4
        }

    def judge_swe_code_change(
        self,
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

        ctx = self._create_swe_server_context()
        kb = ctx.kb
        service_cls = self._explanation_service_cls or ExplanationService
        service = service_cls(kb=kb, config=ctx.config)

        return service.explain_change(
            swe_context=swe_context,
            original_code=original_code,
            modified_code=modified_code,
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


class SweMcpToolsRegistrar:
    """Class-based MCP registration entry point for SWE tools."""

    def __init__(
        self,
        mcp: Any,
        create_swe_server_context: Callable[..., Any],
        planner_cls: Optional[Type[Any]] = None,
        explanation_service_cls: Optional[Type[Any]] = None,
    ) -> None:
        self._mcp = mcp
        self._registry = SweMcpToolRegistry(
            create_swe_server_context=create_swe_server_context,
            planner_cls=planner_cls,
            explanation_service_cls=explanation_service_cls,
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
