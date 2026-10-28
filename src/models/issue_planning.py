from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class IssueEvidence(BaseModel):
    source_id: str
    url: str = ""
    author: str = ""
    author_association: str = ""
    created_at: str | None = None
    updated_at: str | None = None
    body: str


class IssueDiscussion(BaseModel):
    title: str
    evidence: list[IssueEvidence]
    fingerprint: str
    fetched_comments: int = 0
    omitted_comments: int = 0
    omitted_blocks: int = 0
    cutoff: str | None = None
    notes: list[str] = Field(default_factory=list)


class EvidenceClaim(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    evidence_ids: list[str] = Field(min_length=1, max_length=24)


class IssueRequirement(EvidenceClaim):
    requirement_id: str = Field(min_length=1)
    acceptance_check: str = Field(min_length=1, max_length=2000)


class IssueSummary(BaseModel):
    observed_behavior: list[EvidenceClaim] = Field(max_length=16)
    expected_behavior: list[EvidenceClaim] = Field(max_length=16)
    reproduction_steps: list[EvidenceClaim] = Field(max_length=16)
    requirements: list[IssueRequirement] = Field(min_length=1, max_length=32)
    constraints: list[EvidenceClaim] = Field(max_length=16)
    non_goals: list[EvidenceClaim] = Field(max_length=16)
    unresolved_questions: list[EvidenceClaim] = Field(max_length=16)


class NfrDiscovery(BaseModel):
    nfr_id: str
    evidence_ids: list[str] = Field(min_length=1, max_length=24)
    rationale: str = Field(min_length=1, max_length=2000)


class IssueUnderstanding(BaseModel):
    summary: IssueSummary
    nfr_discovery: list[NfrDiscovery] = Field(min_length=1, max_length=16)


class ImplementationStep(BaseModel):
    step_id: str = Field(min_length=1)
    requirement_ids: list[str] = Field(min_length=1, max_length=32)
    target_file: str
    symbol: str = Field(min_length=1)
    action: Literal["reuse", "modify", "create"]
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)
    depends_on: list[str] = Field(max_length=31)
    validation: list[str] = Field(min_length=1, max_length=16)


class GroundedImplementationPlan(BaseModel):
    high_level_steps: list[str] = Field(min_length=1, max_length=32)
    implementation_plan: list[ImplementationStep] = Field(min_length=1, max_length=32)
