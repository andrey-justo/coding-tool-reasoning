from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, RootModel

from src.models.utility_decisions import NonEmptyText, UtilityDecision


class AgentAction(UtilityDecision):
    rationale: NonEmptyText
    notes: str = Field(default="", max_length=12000)


class ReadSource(AgentAction):
    action: Literal["read_source"]
    path: NonEmptyText
    version: Literal["current", "baseline", "initial_generated"] = "current"
    start_line: int = Field(default=1, ge=1)
    end_line: int = Field(default=400, ge=1)


class SearchSources(AgentAction):
    action: Literal["search_sources"]
    query: NonEmptyText


class InspectSource(AgentAction):
    action: Literal["inspect_source"]
    path: NonEmptyText
    lines: list[Annotated[int, Field(ge=1)]] = Field(default_factory=list)


class SourceEdit(UtilityDecision):
    path: NonEmptyText
    source_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    before: str
    after: str


class EditSources(AgentAction):
    action: Literal["edit_sources"]
    edits: list[SourceEdit] = Field(min_length=1)


class VerifySources(AgentAction):
    action: Literal["verify"]


class RestoreSnapshot(AgentAction):
    action: Literal["restore_snapshot"]
    snapshot_id: int = Field(ge=0)


class FinishRepair(AgentAction):
    action: Literal["finish"]
    snapshot_id: int = Field(ge=0)
    requirements_review: NonEmptyText


class StopRepair(AgentAction):
    action: Literal["stop"]


class BranchIntent(UtilityDecision):
    goal: NonEmptyText
    edit_budget: int = Field(ge=1, le=25)


class ForkBranches(AgentAction):
    action: Literal["fork_branches"]
    branches: list[BranchIntent] = Field(min_length=2)


class RepairAgentDecision(
    RootModel[
        Annotated[
            ReadSource
            | SearchSources
            | InspectSource
            | EditSources
            | VerifySources
            | RestoreSnapshot
            | FinishRepair
            | StopRepair
            | ForkBranches,
            Field(discriminator="action"),
        ]
    ]
):
    pass
