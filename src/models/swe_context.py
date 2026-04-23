from typing import List, Optional

from pydantic import BaseModel, Field

from .code_gen_plan import CodeGenPlan


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
