from typing import List, Literal

from pydantic import BaseModel, Field

from src.models.code_gen_plan import CodeGenPlan


class NfrImpact(BaseModel):
    """Impact of the change on a single NFR dimension."""

    nfr: str = Field(
        description="Name of the NFR (e.g., Maintainability, Reliability)."
    )
    verdict: str = Field(
        description=(
            "Short label for the overall effect on this NFR, such as "
            "'improved', 'neutral', or 'regressed'."
        )
    )
    reasoning: str = Field(description="Explanation of why the verdict was reached.")


class SweCodeChangeExplanation(BaseModel):
    """Structured explanation for a code change, aligned with Plan4Code Stage 2."""

    plan: CodeGenPlan = Field(description="The planning artifact produced in Stage 1.")
    overall_verdict: Literal[
        "acceptable", "risky", "rejected", "manual-review-required"
    ] = Field(
        description=(
            "High-level verdict: 'acceptable' (aligns with plan and NFRs), "
            "'risky' (concerns present, not blocking), 'rejected' (does not align "
            "with plan or regresses NFRs), or 'manual-review-required' (automated "
            "judgment failed)."
        )
    )
    confidence: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description=(
            "Judge's self-reported confidence in [0, 1] for the overall_verdict. "
            "Used as a dependent variable for RQ2 (reproducibility) and "
            "RQ3 (prompt-variation robustness)."
        ),
    )
    rationale: str = Field(
        description=(
            "Narrative rationale describing why the change is appropriate, "
            "referencing SWE principles, practices, and smells when helpful."
        )
    )
    nfr_impacts: List[NfrImpact] = Field(
        default_factory=list,
        description="Per-NFR impact assessment derived from the taxonomy and code diff.",
    )
    risks: List[str] = Field(
        default_factory=list,
        description="Potential risks, regressions, or unsafe aspects of the change.",
    )
    recommended_tests: List[str] = Field(
        default_factory=list,
        description="Concrete tests or checks the developer should run to validate the change.",
    )
    llm_prompt: str | None = Field(
        default=None,
        description="Prompt text sent to the explanation/judge LLM call.",
    )
    llm_raw_response: str | None = Field(
        default=None,
        description="Raw text returned by the explanation LLM call before structured parsing.",
    )
