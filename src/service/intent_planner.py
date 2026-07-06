import json
from typing import List, Optional, Tuple

from src.llm_client.multi_model_llm_client import MultiModelLLMClient
from src.models.intent_planning_result import IntentPlanningResult
from src.models.swe_config import SweMcpConfig
from src.service.swe_taxonomy_service import SweKnowledgeBase

_DEFAULT_NFR_FOCUS = ["Maintainability", "Readability"]


class IntentPlanner:
    """Stage 1 planner: intent extraction + action planning.

    This component corresponds to the "Intent Extractor" and
    "Intent Action" blocks in the Plan4Code poster, but uses the
    existing SWE taxonomy rather than a separate ontology graph.
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
    ) -> IntentPlanningResult:
        """Create a taxonomy-guided high-level plan for a code change.

        - First, infer / normalize the NFR focus (Intent Extractor)
        - Then, call the LLM with Chain-of-Thought style instructions and
          a RAG-style summary of the SWE taxonomy (Intent Action)
        """

        effective_target_language = target_language
        if (
            not effective_target_language
            and self.config.planning.infer_target_language_when_missing
        ):
            effective_target_language = self._infer_target_language(problem_description)

        effective_nfr_focus, resolved_ids = self._resolve_nfr_focus(
            problem_description=problem_description,
            nfr_focus=nfr_focus,
        )

        steps, llm_prompt, llm_raw_response = self._generate_steps_with_llm(
            problem_description=problem_description,
            target_language=effective_target_language,
            nfr_focus=effective_nfr_focus,
            resolved_nfr_ids=resolved_ids,
            user_prompt_data=user_prompt_data,
        )

        return IntentPlanningResult(
            nfr_focus=effective_nfr_focus,
            resolved_nfr_ids=resolved_ids,
            high_level_steps=steps,
            inferred_target_language=effective_target_language,
            llm_prompt=llm_prompt,
            llm_raw_response=llm_raw_response,
        )

    # ------------------------- helpers ---------------------------
    def _resolve_nfr_focus(
        self,
        problem_description: str,
        nfr_focus: Optional[List[str]] = None,
    ) -> Tuple[List[str], List[str]]:
        """Infer / normalize the NFR focus and map it to taxonomy IDs.

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
        focus, resolved_ids = self._expand_nfr_candidates_via_taxonomy(
            focus=focus,
            resolved_ids=resolved_ids,
        )
        return focus, resolved_ids

    def _expand_nfr_candidates_via_taxonomy(
        self,
        focus: List[str],
        resolved_ids: List[str],
    ) -> Tuple[List[str], List[str]]:
        """Expand inferred intents by traversing NFR-to-NFR taxonomy links.

        Some NFR candidates imply additional NFRs via linked taxonomy edges.
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

        text_lower = text.lower()
        language_markers = [
            ("python", ["python", "py ", "pytest", "pydantic", "django", "fastapi"]),
            ("javascript", ["javascript", "js ", "node", "npm", "express", "react"]),
            ("typescript", ["typescript", "ts ", "tsx", "nestjs", "angular"]),
            ("java", [" java", "spring", "maven", "gradle", "junit"]),
            ("c#", ["c#", "dotnet", ".net", "asp.net"]),
            ("go", [" golang", " go ", "goroutine", "go.mod"]),
            ("rust", ["rust", "cargo", "tokio"]),
            ("ruby", ["ruby", "rails", "rspec"]),
            ("php", ["php", "laravel", "composer"]),
            ("kotlin", ["kotlin", "ktor"]),
            ("swift", ["swift", "xcode", "ios"]),
        ]

        for language, markers in language_markers:
            for marker in markers:
                if marker in text_lower:
                    return language
        return None

    def _generate_steps_with_llm(
        self,
        problem_description: str,
        target_language: Optional[str],
        nfr_focus: List[str],
        resolved_nfr_ids: List[str],
        user_prompt_data: Optional[str],
    ) -> Tuple[List[str], str, Optional[str]]:
        """Use the LLM with taxonomy RAG to propose high-level steps.

        If the LLM output cannot be parsed as JSON, we fall back to a
        deterministic default step list so the MCP tool remains robust.
        """

        taxonomy_summary = self.kb.summarize_for_prompt(
            resolved_nfr_ids,
            depth=self.config.taxonomy.relationship_depth,
        )
        max_steps = self.config.planning.max_steps
        language_label = target_language or "the project"

        # Build a human-readable lifecycle-phase guide from workflow.stages so
        # the LLM knows which SE phases the steps should be distributed across.
        stages = self.config.workflow.stages or []
        stages_guidance = ""
        if stages:
            stages_list = "\n".join(f"  - {s}" for s in stages)
            stages_guidance = (
                "The plan should produce at least one step for each of the\n"
                "following software-engineering lifecycle phases (workflow\n"
                "stages configured for this project):\n"
                f"{stages_list}\n\n"
            )

        additional_user_context = (
            f"Additional user prompt data:\n{user_prompt_data}\n\n"
            if user_prompt_data
            else ""
        )

        prompt_header = (
            "You are a senior software engineer planning safe,\n"
            f"step-by-step code changes in a {language_label} codebase.\n\n"
            f"User request (natural language):\n{problem_description}\n\n"
            f"{additional_user_context}"
            f"Non-functional requirements to prioritize: {', '.join(nfr_focus) or 'None specified'}.\n\n"
            f"{stages_guidance}"
            "Here is structured software-engineering taxonomy data with NFRs,\n"
            "principles, practices, and code smells that are relevant to this\n"
            "request. Use it as background knowledge when reasoning:\n\n"
            f"{taxonomy_summary}\n\n"
            "Think in a chain-of-thought about what changes are needed, then\n"
            "produce a concise JSON object describing the high-level plan.\n"
            "The JSON must have exactly this shape and no extra keys or text:\n\n"
            "{\n"
            '  "high_level_steps": [\n'
            '    "Step 1 ...",\n'
            '    "Step 2 ..."\n'
            "  ]\n"
            "}\n\n"
        )

        prompt_footer = (
            "Do NOT include markdown, explanations, or any text before or\n"
            "after the JSON. The steps should be phrased as imperative\n"
            "actions that another coding agent could execute (e.g., 'Scan\n"
            "existing controller classes for long methods related to X').\n"
            f"Limit yourself to at most {max_steps} high-level steps."
        )

        prompt = prompt_header + prompt_footer

        raw: Optional[str] = None
        try:
            raw = self.llm_client.chat(prompt)
            data = json.loads(raw)
            steps = data.get("high_level_steps") or []
            if isinstance(steps, list) and all(isinstance(s, str) for s in steps):
                # Basic sanity filter to avoid empty or trivial output.
                cleaned = [s.strip() for s in steps if s and s.strip()]
                return cleaned[:max_steps], prompt, raw
        except Exception:
            # Fall through to deterministic default plan.
            pass

        # Fallback: deterministic taxonomy-aware steps.
        default_steps = [
            "Understand the current behavior and constraints from the existing code.",
            "Identify which NFRs are most impacted using the SWE taxonomy.",
            "Locate relevant principles, practices, and smells connected to those NFRs.",
            "Design small, incremental changes that improve the targeted NFRs without breaking behavior.",
            "Apply the changes in small commits, verifying behavior after each change.",
            "Update or add tests to cover both the original and new behavior.",
        ]
        return default_steps, prompt, raw
