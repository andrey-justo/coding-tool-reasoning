from typing import List, Optional

from pydantic import BaseModel, Field


class CodeGenPlan(BaseModel):
    """High-level plan for a SWE code generation/refactoring task."""

    problem_description: str = Field(description="Natural language description of the code change.")
    target_language: Optional[str] = Field(
        default=None, description="Target programming language (e.g., C#, Python)."
    )
    nfr_focus: List[str] = Field(
        default_factory=list,
        description="List of NFRs to prioritize (by name or ID, e.g., Maintainability, Readability).",
    )
    high_level_steps: List[str] = Field(
        default_factory=list,
        description="Ordered steps the agent should follow when applying the change.",
    )
    related_entities: List[str] = Field(
        default_factory=list,
        description="IDs of SWE taxonomy entities (principles, practices, smells) relevant to this plan.",
    )

