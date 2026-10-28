import json
import logging
from typing import List, Optional, Tuple

from src.llm_client.multi_model_llm_client import MultiModelLLMClient
from src.models.intent_planning_result import IntentPlanningResult
from src.models.issue_planning import (
    GroundedImplementationPlan,
    ImplementationStep,
    IssueDiscussion,
    IssueUnderstanding,
)
from src.models.swe_config import SweMcpConfig
from src.service.language_detection import infer_language_from_text
from src.service.swe_knowledge_base_service import SweKnowledgeBase
from src.service.issue_planning_service import IssuePlanningService
from src.service.utility_llm_service import UtilityLlmService

_DEFAULT_NFR_FOCUS = ["Maintainability", "Readability"]
logger = logging.getLogger(__name__)


class IntentPlanner:
    """Stage 1 planner: intent extraction + action planning.

    This component corresponds to the "Intent Extractor" and
    "Intent Action" blocks in the Plan4Code poster, but uses the
    existing SWE knowledge base rather than a separate ontology graph.
    """

    def __init__(
        self,
        kb: SweKnowledgeBase,
        llm_client: Optional[MultiModelLLMClient] = None,
        config: Optional[SweMcpConfig] = None,
    ) -> None:
        self.kb = kb
        self.llm_client = llm_client or MultiModelLLMClient()
        self.config = config or SweMcpConfig()

    # ------------------------- public API -------------------------
    def plan(
        self,
        problem_description: str,
        target_language: Optional[str] = None,
        nfr_focus: Optional[List[str]] = None,
        user_prompt_data: Optional[str] = None,
        issue_discussion: Optional[IssueDiscussion] = None,
        baseline_code_by_file: Optional[dict[str, str]] = None,
    ) -> IntentPlanningResult:
        """Create a knowledge-base-guided high-level plan for a code change.

        - First, infer / normalize the NFR focus (Intent Extractor)
        - Then, call the LLM with Chain-of-Thought style instructions and
          a RAG-style summary of the SWE knowledge base (Intent Action)
        """

        effective_target_language = target_language
        if (
            not effective_target_language
            and self.config.planning.infer_target_language_when_missing
        ):
            effective_target_language = self._infer_target_language(problem_description)

        understanding = None
        baseline_context = {}
        discovery_source = "legacy"
        requested_focus = nfr_focus
        if issue_discussion is not None:
            planning_service = IssuePlanningService(self.kb, self.llm_client)
            baseline_context = planning_service.repository_context(
                baseline_code_by_file or {}
            )
            understanding = planning_service.understand(issue_discussion)
            requested_focus = [
                self.kb.nodes[item.nfr_id].name or item.nfr_id
                for item in understanding.nfr_discovery
            ]
            discovery_source = "issue_evidence"
            if nfr_focus:
                logger.warning(
                    "Explicit NFR override replaces issue-discovered focus for this manual request"
                )
                requested_focus = nfr_focus
                discovery_source = "explicit_override"
        effective_nfr_focus, resolved_ids = self._resolve_nfr_focus(
            problem_description=problem_description,
            nfr_focus=requested_focus,
        )

        steps, llm_prompt, llm_raw_response, implementation_plan = (
            self._generate_steps_with_llm(
                problem_description=problem_description,
                target_language=effective_target_language,
                nfr_focus=effective_nfr_focus,
                resolved_nfr_ids=resolved_ids,
                user_prompt_data=user_prompt_data,
                understanding=understanding,
                baseline_context=baseline_context,
            )
        )

        return IntentPlanningResult(
            nfr_focus=effective_nfr_focus,
            resolved_nfr_ids=resolved_ids,
            high_level_steps=steps,
            inferred_target_language=effective_target_language,
            llm_prompt=llm_prompt,
            llm_raw_response=llm_raw_response,
            issue_summary=understanding.summary if understanding else None,
            issue_discussion=issue_discussion,
            nfr_discovery=understanding.nfr_discovery if understanding else [],
            nfr_discovery_source=discovery_source,
            implementation_plan=implementation_plan,
            baseline_context=baseline_context,
        )

    # ------------------------- helpers ---------------------------
    def _resolve_nfr_focus(
        self,
        problem_description: str,
        nfr_focus: Optional[List[str]] = None,
    ) -> Tuple[List[str], List[str]]:
        """Infer / normalize the NFR focus and map it to knowledge base IDs.

        - If explicit NFRs are provided, use them.
        - Otherwise, try to detect NFRs mentioned in the description.
        - Fallback to a default pair (maintainability + readability).
        """

        if nfr_focus:
            focus = list(nfr_focus)
        else:
            focus = self._infer_nfrs_from_text(problem_description)
            if not focus:
                focus = list(
                    self.config.planning.default_nfr_focus or _DEFAULT_NFR_FOCUS
                )

        resolved_ids = self.kb.find_nfr_ids(focus)
        focus, resolved_ids = self._expand_nfr_candidates_via_knowledge_base(
            focus=focus,
            resolved_ids=resolved_ids,
        )
        return focus, resolved_ids

    def _expand_nfr_candidates_via_knowledge_base(
        self,
        focus: List[str],
        resolved_ids: List[str],
    ) -> Tuple[List[str], List[str]]:
        """Expand inferred intents by traversing NFR-to-NFR knowledge base links.

        Some NFR candidates imply additional NFRs via linked knowledge base edges.
        This loop runs up to ``planning.max_intent_inference_loops`` and stops
        early when no new NFR candidates are discovered.
        """

        max_loops = self.config.planning.max_intent_inference_loops
        if max_loops <= 0:
            return focus, resolved_ids

        focus_seen = {f.lower() for f in focus}
        nfr_id_seen = set(resolved_ids)
        all_edges = self.kb.edges

        for _ in range(max_loops):
            new_ids: List[str] = []

            for nfr_id in list(nfr_id_seen):
                for edge in all_edges:
                    # Traverse both directions so inverse links are also useful.
                    if edge.source_id == nfr_id:
                        neighbor_id = edge.target_id
                    elif edge.target_id == nfr_id:
                        neighbor_id = edge.source_id
                    else:
                        continue

                    neighbor = self.kb.nodes.get(neighbor_id)
                    if not neighbor or neighbor.type.upper() != "NFR":
                        continue
                    if neighbor.id in nfr_id_seen:
                        continue
                    nfr_id_seen.add(neighbor.id)
                    new_ids.append(neighbor.id)

                    # Keep focus labels human-readable while preserving order.
                    preferred_label = (
                        neighbor.name or neighbor.nfr_category or neighbor.id
                    )
                    label_key = preferred_label.lower()
                    if label_key not in focus_seen:
                        focus.append(preferred_label)
                        focus_seen.add(label_key)

            if not new_ids:
                break

        return focus, list(nfr_id_seen)

    def _infer_nfrs_from_text(self, text: str) -> List[str]:
        text_lower = text.lower()
        candidates: List[str] = []

        # Look for known NFR names/categories mentioned in the request.
        for node in self.kb.get_all_nfrs():
            name = (node.name or "").lower()
            category = (node.nfr_category or "").lower()
            if name and name in text_lower:
                candidates.append(node.name)
            elif category and category in text_lower:
                candidates.append(node.nfr_category)

        # Preserve order but remove duplicates.
        seen = set()
        unique: List[str] = []
        for c in candidates:
            key = c.lower()
            if key in seen:
                continue
            seen.add(key)
            unique.append(c)
        return unique

    def _infer_target_language(self, text: str) -> Optional[str]:
        """Infer target language from user request text when not explicit."""
        return infer_language_from_text(text)

    def _generate_steps_with_llm(
        self,
        problem_description: str,
        target_language: Optional[str],
        nfr_focus: List[str],
        resolved_nfr_ids: List[str],
        user_prompt_data: Optional[str],
        understanding: Optional[IssueUnderstanding] = None,
        baseline_context: Optional[dict] = None,
    ) -> Tuple[List[str], str, Optional[str], List[ImplementationStep]]:
        """Use the LLM with knowledge base RAG to propose high-level steps.

        If the LLM output cannot be parsed as JSON, we fall back to a
        deterministic default step list so the MCP tool remains robust.
        """

        knowledge_base_summary = self.kb.summarize_for_prompt(
            resolved_nfr_ids,
            depth=self.config.knowledge_base.relationship_depth,
        )
        max_steps = self.config.planning.max_steps
        utility = UtilityLlmService(self.llm_client)
        prompt_data = {
            "request": problem_description,
            "language": target_language or "the project",
            "Additional user prompt data": user_prompt_data,
            "nfr_focus": nfr_focus,
            "SWE knowledge-base endorsement context": knowledge_base_summary,
            "lifecycle_stages": self.config.workflow.stages or [],
            "max_steps": max_steps,
        }
        prompt = utility.render("high_level_plan", prompt_data)
        if understanding is not None:
            prompt = utility.render(
                "implementation_plan",
                {
                    **prompt_data,
                    "issue_understanding": understanding.model_dump(),
                    "baseline_declarations": baseline_context,
                },
                GroundedImplementationPlan,
            )

        raw: Optional[str] = None
        try:
            raw = self.llm_client.chat(prompt)
            if understanding is not None:

                def validate_response(response: str) -> GroundedImplementationPlan:
                    structured = GroundedImplementationPlan.model_validate_json(
                        response
                    )
                    IssuePlanningService.validate_implementation(
                        structured,
                        understanding,
                        baseline_context or {},
                        llm_client=self.llm_client,
                    )
                    return structured

                try:
                    structured = validate_response(raw)
                except ValueError as error:
                    logger.warning(
                        "Grounded plan failed validation; requesting one correction: %s",
                        error,
                    )
                    prompt += "\n" + utility.render(
                        "implementation_plan_correction",
                        {
                            "validation_error": str(error),
                            "previous_invalid_plan": raw[:24000],
                        },
                    )
                    raw = self.llm_client.chat(prompt)
                    structured = validate_response(raw)
                return (
                    structured.high_level_steps[:max_steps],
                    prompt,
                    raw,
                    structured.implementation_plan,
                )
            data = json.loads(raw)
            steps = data.get("high_level_steps") or []
            if isinstance(steps, list) and all(isinstance(s, str) for s in steps):
                # Basic sanity filter to avoid empty or trivial output.
                cleaned = [s.strip() for s in steps if s and s.strip()]
                return cleaned[:max_steps], prompt, raw, []
        except Exception:
            logger.exception("Implementation planning failed")
            if understanding is not None:
                raise

        # Fallback: deterministic knowledge base-aware steps.
        default_steps = [
            "Understand the current behavior and constraints from the existing code.",
            "Identify which NFRs are most impacted using the SWE knowledge base.",
            "Locate relevant principles, practices, and smells connected to those NFRs.",
            "Design small, incremental changes that improve the targeted NFRs without breaking behavior.",
            "Apply the changes in small commits, verifying behavior after each change.",
            "Update or add tests to cover both the original and new behavior.",
        ]
        return default_steps, prompt, raw, []
