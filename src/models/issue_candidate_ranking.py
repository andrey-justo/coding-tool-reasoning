from typing import List, Optional

from pydantic import BaseModel, Field


class PullRequestContext(BaseModel):
    """Input context describing the current pull request to analyze."""

    title: str = Field(description="Current pull request title.")
    description: Optional[str] = Field(
        default=None,
        description="Current pull request body/description.",
    )
    changed_files: List[str] = Field(
        default_factory=list,
        description="Repository-relative changed file paths in the PR.",
    )


class IssueCandidate(BaseModel):
    """Issue metadata used by the ranking entrypoint."""

    issue_id: str = Field(description="Unique issue identifier.")
    title: str = Field(description="Issue title.")
    body: Optional[str] = Field(default=None, description="Issue description/body.")
    labels: List[str] = Field(
        default_factory=list,
        description="Issue labels used as additional ranking signals.",
    )
    related_files: List[str] = Field(
        default_factory=list,
        description="Optional issue-related file paths if already known.",
    )


class RankedIssueCandidate(BaseModel):
    """Single ranked issue candidate with score details."""

    issue_id: str = Field(description="Unique issue identifier.")
    title: str = Field(description="Issue title.")
    score: float = Field(ge=0.0, le=1.0, description="Overall relevance score.")
    matched_nfrs: List[str] = Field(
        default_factory=list,
        description="NFRs from PR planning that are also represented in this issue.",
    )
    matched_files: List[str] = Field(
        default_factory=list,
        description="PR files that overlap with issue-related files.",
    )
    reasons: List[str] = Field(
        default_factory=list,
        description="Human-readable explanation for the ranking score.",
    )


class IssueCandidateRankingResult(BaseModel):
    """Result payload for best issue candidate selection based on a PR."""

    inferred_nfr_focus: List[str] = Field(
        default_factory=list,
        description="NFR focus inferred from the current pull request context.",
    )
    total_candidates: int = Field(description="Total input issue candidates processed.")
    returned_candidates: int = Field(description="Number of candidates returned.")
    ranked_candidates: List[RankedIssueCandidate] = Field(
        default_factory=list,
        description="Ranked issue candidates sorted by descending score.",
    )