import json
from typing import List, Optional

from .swe_taxonomy_service import SweKnowledgeBase
from ..llm_client.multi_model_llm_client import MultiModelLLMClient
from ..models.code_gen_plan import CodeGenPlan
from ..models.swe_config import SweMcpConfig
from ..models.swe_context import SweContext
from ..models.swe_explanation import NfrImpact, SweCodeChangeExplanation


class ExplanationService:
    """Stage 2: taxonomy-guided judging and explanation of code changes.

    This service corresponds to the Plan4Code "Judge & Test" plus
    "Explanation Generator" blocks, using the SWE taxonomy (not ontologies)
    and an LLM to produce a structured explanation aligned with the
    Stage 1 planning artifact.
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

    def explain_change(
        self,
        swe_context: SweContext,
        original_code: str,
        modified_code: str,
    ) -> SweCodeChangeExplanation:
        plan = swe_context.plan

        # Collect taxonomy context for the entities/nfrs referenced in the plan.
        related_ids: List[str] = list(plan.related_entities or [])
        if not related_ids and plan.nfr_focus:
            related_ids = self.kb.find_nfr_ids(plan.nfr_focus)

        taxonomy_summary = self.kb.summarize_for_prompt(
            related_ids,
            depth=self.config.taxonomy.relationship_depth,
        )

        prompt = self._build_prompt(
            swe_context=swe_context,
            original_code=original_code,
            modified_code=modified_code,
            taxonomy_summary=taxonomy_summary,
        )

        try:
            raw = self.llm_client.chat(prompt)
            data = json.loads(raw)
            return self._from_llm_json(plan_json=plan.model_dump(), data=data)
        except Exception:
            # Fallback: produce a conservative explanation that at least
            # records the plan and points the user at manual review.
            return SweCodeChangeExplanation(
                plan=plan,
                overall_verdict="manual-review-required",
                rationale=(
                    "The explanation model could not parse a structured response. "
                    "Please review the code diff manually and re-run the judge tool."
                ),
                nfr_impacts=[],
                risks=[
                    "Automated explanation failed; ensure tests pass and that the change "
                    "matches the high-level steps from the plan.",
                ],
                recommended_tests=[
                    "Run existing unit and integration tests relevant to the modified modules.",
                ],
            )

    # ------------------------- helpers ---------------------------
    def _build_prompt(
        self,
        swe_context: SweContext,
        original_code: str,
        modified_code: str,
        taxonomy_summary: str,
    ) -> str:
        plan = swe_context.plan
        nfr_focus_label = (
            ", ".join(plan.nfr_focus)
            if plan.nfr_focus
            else "(none explicitly specified)"
        )

        strictness = self.config.judging.strictness
        strictness_text = (
            "lenient"
            if strictness < 0.33
            else "strict" if strictness > 0.66 else "balanced"
        )

        header = (
            "You are a senior software engineer acting as a judge for code changes.\n\n"
            "The change you are judging was planned using a SWE taxonomy-guided planner.\n"
            "Your task is to assess whether the actual code modification follows the plan,\n"
            "aligns with the developer's intent, and how it impacts key non-functional\n"
            "requirements (NFRs).\n\n"
            f"Judging strictness (0-1): {strictness:.2f} ({strictness_text}).\n\n"
        )

        sections = [
            f"=== Problem Description ===\n{plan.problem_description}\n",
            f"\n=== NFR Focus ===\n{nfr_focus_label}\n",
            "\n=== High-Level Plan Steps ===\n"
            + "\n".join(f"- {step}" for step in plan.high_level_steps)
            + "\n",
            "\n=== Taxonomy Context (SWE taxonomy, not ontologies) ===\n"
            + f"{taxonomy_summary}\n",
            "\n=== SWE/NFR Summary (RAG-style context) ===\n"
            + f"{swe_context.swe_summary}\n",
        ]

        # Optional, user-provided security context (e.g., threat models,
        # security guidelines, or configuration snippets) that can be fetched
        # and injected by the client when Security is a primary concern.
        if swe_context.security_context:
            sections.append(
                "\n=== Additional Security Context (client-provided) ===\n"
                + f"{swe_context.security_context}\n"
            )

        sections.append(f"\n=== Original Code ===\n{original_code}\n")
        sections.append(f"\n=== Modified Code ===\n{modified_code}\n")

        instructions = (
            "\nAnalyse the differences step by step, referencing the SWE taxonomy "
            "concepts when relevant (NFRs, principles, practices, smells). Then "
            "produce a concise JSON object with this exact shape and nothing "
            "before or after it:\n\n"
            "{\n"
            '  "overall_verdict": "acceptable|risky|rejected|manual-review-required",\n'
            '  "rationale": "High-level explanation in one or two paragraphs...",\n'
            '  "nfr_impacts": [\n'
            "    {\n"
            '      "nfr": "Maintainability",\n'
            '      "verdict": "improved|neutral|regressed",\n'
            '      "reasoning": "Short reasoning referencing taxonomy concepts..."\n'
            "    }\n"
            "  ],\n"
            '  "risks": [\n'
            '    "Short bullet-style risk description..."\n'
            "  ],\n"
            '  "recommended_tests": [\n'
            '    "Concrete test or check the developer should run..."\n'
            "  ]\n"
            "}\n\n"
            "Do NOT wrap the JSON in markdown and do NOT include commentary "
            "outside the JSON block."
        )

        return header + "".join(sections) + instructions

    def _from_llm_json(self, plan_json: dict, data: dict) -> SweCodeChangeExplanation:
        overall_verdict = str(data.get("overall_verdict", "manual-review-required"))
        rationale = str(data.get("rationale", ""))

        nfr_impacts_data = data.get("nfr_impacts") or []
        nfr_impacts: List[NfrImpact] = []
        for item in nfr_impacts_data:
            try:
                nfr_impacts.append(
                    NfrImpact(
                        nfr=str(item.get("nfr", "")),
                        verdict=str(item.get("verdict", "")),
                        reasoning=str(item.get("reasoning", "")),
                    )
                )
            except Exception:
                continue

        risks_raw = data.get("risks") or []
        risks = [str(r) for r in risks_raw if str(r).strip()]
        # Respect configuration limit on the number of risk bullet points.
        risks = risks[: self.config.judging.max_risks]

        tests_raw = data.get("recommended_tests") or []
        recommended_tests = [str(t) for t in tests_raw if str(t).strip()]

        return SweCodeChangeExplanation(
            plan=CodeGenPlan.model_validate(plan_json),
            overall_verdict=overall_verdict,
            rationale=rationale,
            nfr_impacts=nfr_impacts,
            risks=risks,
            recommended_tests=recommended_tests,
        )
