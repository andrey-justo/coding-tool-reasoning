from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class UtilityDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class SemanticReview(UtilityDecision):
    approved: bool = Field(
        description="True only with an empty concerns list; otherwise reject with explicit concerns."
    )
    rationale: NonEmptyText
    concerns: list[NonEmptyText] = Field(
        description="Blocking concerns only. Must be empty for approval and nonempty for rejection."
    )

    @model_validator(mode="after")
    def consistent_verdict(self) -> SemanticReview:
        if self.approved == bool(self.concerns):
            raise ValueError(
                "Approval requires no concerns; rejection requires explicit concerns."
            )
        return self


class DiagnosticSymbols(UtilityDecision):
    symbols: list[NonEmptyText] = Field(max_length=32)


class SymbolContextSelection(UtilityDecision):
    candidate_ids: list[int]
    rationale: NonEmptyText


class DiagnosticContextMatch(UtilityDecision):
    message_index: int = Field(ge=0)
    candidate_ids: list[int]


class DiagnosticContextSelection(UtilityDecision):
    matches: list[DiagnosticContextMatch]
    rationale: NonEmptyText
