from typing import List, Optional

from pydantic import BaseModel, Field

from src.models.code_gen_plan import CodeGenPlan


class SweContext(BaseModel):
    """Context payload to inject into LLM prompts for code generation."""

    plan: CodeGenPlan
    swe_summary: str = Field(
        description="Human-readable summary of NFRs and relationships."
    )
    templates: List[dict] = Field(
        default_factory=list,
        description="Optional templates and design artifacts (e.g., reliability patterns).",
    )
    security_context: Optional[str] = Field(
        default=None,
        description=(
            "Optional additional security-related context fetched by the client "
            "(e.g., threat models, security guidelines, or config snippets) to "
            "augment planning and explanations when Security is in focus."
        ),
    )
    related_subjects: List[str] = Field(
        default_factory=list,
        description=(
            "Purpose-matched knowledge subjects resolved from the planned change "
            "and used to attach multiple relevant knowledge entries."
        ),
    )
    attached_knowledge: List[dict] = Field(
        default_factory=list,
        description=(
            "Knowledge entries selected from concern data (knowledge/data) for "
            "the explanation workflow."
        ),
    )
