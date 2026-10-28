from typing import Any, List, Optional

from pydantic import BaseModel, Field
from src.models.issue_planning import (
    ImplementationStep,
    IssueDiscussion,
    IssueSummary,
    NfrDiscovery,
)


class CodeGenPlan(BaseModel):
    """High-level plan for a SWE code generation/refactoring task."""

    problem_description: str = Field(
        description="Natural language description of the code change."
    )
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
        description="IDs of SWE knowledge base entities (principles, practices, smells) relevant to this plan.",
    )
    llm_prompt: Optional[str] = Field(
        default=None,
        description="Prompt text sent to the planner LLM call.",
    )
    llm_raw_response: Optional[str] = Field(
        default=None,
        description="Raw text returned by the planner LLM call before structured parsing.",
    )
    issue_summary: Optional[IssueSummary] = None
    issue_discussion: Optional[IssueDiscussion] = None
    nfr_discovery: List[NfrDiscovery] = Field(default_factory=list)
    nfr_discovery_source: str = "legacy"
    implementation_plan: List[ImplementationStep] = Field(default_factory=list)
    baseline_context: dict[str, Any] = Field(default_factory=dict)
