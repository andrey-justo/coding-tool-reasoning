from dataclasses import dataclass, field
from typing import Any, List, Optional
from src.models.issue_planning import (
    ImplementationStep,
    IssueDiscussion,
    IssueSummary,
    NfrDiscovery,
)


@dataclass
class IntentPlanningResult:
    """Output of Stage 1 intent planning.

    This helper structure bridges the natural-language request and the
    `CodeGenPlan` model used by MCP tools.
    """

    nfr_focus: List[str]
    resolved_nfr_ids: List[str]
    high_level_steps: List[str]
    inferred_target_language: Optional[str] = None
    llm_prompt: Optional[str] = None
    llm_raw_response: Optional[str] = None
    issue_summary: Optional[IssueSummary] = None
    issue_discussion: Optional[IssueDiscussion] = None
    nfr_discovery: List[NfrDiscovery] = field(default_factory=list)
    nfr_discovery_source: str = "legacy"
    implementation_plan: List[ImplementationStep] = field(default_factory=list)
    baseline_context: dict[str, Any] = field(default_factory=dict)
