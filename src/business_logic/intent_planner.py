import json
from dataclasses import dataclass
from typing import List, Optional, Tuple

from .swe_taxonomy_service import SweKnowledgeBase
from ..llm_client.multi_model_llm_client import MultiModelLLMClient
from ..models.swe_config import SweMcpConfig


_DEFAULT_NFR_FOCUS = ["Maintainability", "Readability"]


@dataclass
class IntentPlanningResult:
    """Output of Stage 1 intent planning.

    This is an internal helper structure used by the MCP tools to bridge
    between the natural-language request and the `CodeGenPlan` model.
    """

    nfr_focus: List[str]
    resolved_nfr_ids: List[str]
    high_level_steps: List[str]


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
    ) -> IntentPlanningResult:
        """Create a taxonomy-guided high-level plan for a code change.

        - First, infer / normalize the NFR focus (Intent Extractor)
        - Then, call the LLM with Chain-of-Thought style instructions and
          a RAG-style summary of the SWE taxonomy (Intent Action)
        """

        effective_nfr_focus, resolved_ids = self._resolve_nfr_focus(
            problem_description=problem_description,
            nfr_focus=nfr_focus,
        )

        steps = self._generate_steps_with_llm(
            problem_description=problem_description,
            target_language=target_language,
            nfr_focus=effective_nfr_focus,
            resolved_nfr_ids=resolved_ids,
        )

        return IntentPlanningResult(
            nfr_focus=effective_nfr_focus,
            resolved_nfr_ids=resolved_ids,
            high_level_steps=steps,
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
        return focus, resolved_ids

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

    def _generate_steps_with_llm(
        self,
        problem_description: str,
        target_language: Optional[str],
        nfr_focus: List[str],
        resolved_nfr_ids: List[str],
    ) -> List[str]:
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

        prompt_header = (
            "You are a senior software engineer planning safe,\n"
            f"step-by-step code changes in a {language_label} codebase.\n\n"
            f"User request (natural language):\n{problem_description}\n\n"
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

        try:
            raw = self.llm_client.chat(prompt)
            data = json.loads(raw)
            steps = data.get("high_level_steps") or []
            if isinstance(steps, list) and all(isinstance(s, str) for s in steps):
                # Basic sanity filter to avoid empty or trivial output.
                cleaned = [s.strip() for s in steps if s and s.strip()]
                return cleaned[:max_steps]
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
        return default_steps
