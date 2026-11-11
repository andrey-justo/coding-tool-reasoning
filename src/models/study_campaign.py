from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.models.swe_config import ToolExecutionConfig, VerificationConfig

Identifier = Annotated[str, Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_-]*$")]


class StudyModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class StudyModelProfile(StudyModel):
    alias: str = Field(min_length=1)
    provider: Literal["CopilotSDK", "AzureResponses", "LocalAI"]
    temperature: float | None = Field(default=None, ge=0, le=2)
    seed: int | None = None

    @model_validator(mode="after")
    def supported_controls(self) -> StudyModelProfile:
        if self.provider == "CopilotSDK" and (
            self.temperature is not None or self.seed is not None
        ):
            raise ValueError(
                "CopilotSDK does not support controlled temperature or seed."
            )
        return self


class SubjectBinding(StudyModel):
    subject_id: str | None = None
    issue_url: str | None = None
    base_commit: str | None = Field(default=None, pattern=r"^[a-fA-F0-9]{40}$")
    repo_path: str | None = None
    structural_config: str | None = None
    paraphrases_file: str | None = None
    issue_context_cutoff: str | None = None
    ai_use_approved: bool = False


class StudyExecutionConfig(StudyModel):
    schema_version: Literal[1] = 1
    campaign_config: str
    task_config: str | None
    job_id: str
    study: str
    cohort: str
    slot: str
    repetition: int = Field(ge=1)
    variant: str
    block_key: str
    subject_id: str | None
    issue_url: str | None
    condition: str
    worker: Literal["mcp_supervised", "baseline_prompt_only"]
    strictness: float = Field(ge=0, le=1)
    runtime_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    status: Literal["planned", "blocked"]
    blockers: list[str]


class CohortSpec(StudyModel):
    sets: int = Field(default=3, ge=1)
    tasks_per_set: int = Field(default=10, ge=1)
    legacy_only: bool = False
    import_planned_rq: str | None = None
    bindings: dict[str, SubjectBinding] = Field(default_factory=dict)

    @model_validator(mode="after")
    def known_slots(self) -> CohortSpec:
        slots = {
            f"set{group:02d}-task{task:02d}"
            for group in range(1, self.sets + 1)
            for task in range(1, self.tasks_per_set + 1)
        }
        if not set(self.bindings) <= slots:
            raise ValueError("Cohort bindings refer to unknown task slots.")
        return self


class StudyCondition(StudyModel):
    id: Identifier
    worker: Literal["mcp_supervised", "baseline_prompt_only"]
    strictness: float | None = Field(default=None, ge=0, le=1)

    @model_validator(mode="after")
    def meaningful_strictness(self) -> StudyCondition:
        if self.worker == "baseline_prompt_only" and self.strictness is not None:
            raise ValueError("Supervisor strictness is not a baseline parameter.")
        return self


class StudyComparison(StudyModel):
    id: Identifier
    control: Identifier
    treatment: Identifier


class StudySpec(StudyModel):
    id: Identifier
    rq: str = Field(min_length=1)
    cohort: Identifier
    conditions: list[StudyCondition] = Field(min_length=2)
    comparisons: list[StudyComparison] = Field(min_length=1)
    repetitions: int = Field(default=1, ge=1)
    variants: list[Identifier] = Field(
        default_factory=lambda: ["original"], min_length=1
    )

    @model_validator(mode="after")
    def valid_comparisons(self) -> StudySpec:
        conditions = [condition.id for condition in self.conditions]
        if len(conditions) != len(set(conditions)):
            raise ValueError("Study condition IDs must be unique.")
        if len(self.variants) != len(set(self.variants)):
            raise ValueError("Prompt variant IDs must be unique.")
        comparisons = [comparison.id for comparison in self.comparisons]
        if len(comparisons) != len(set(comparisons)):
            raise ValueError("Comparison IDs must be unique.")
        used = set()
        pairs = set()
        for comparison in self.comparisons:
            if comparison.control == comparison.treatment or not {
                comparison.control,
                comparison.treatment,
            } <= set(conditions):
                raise ValueError(
                    "Comparisons must reference distinct declared conditions."
                )
            pair = frozenset((comparison.control, comparison.treatment))
            if pair in pairs:
                raise ValueError("The same condition comparison is declared twice.")
            pairs.add(pair)
            used.update(pair)
        if used != set(conditions):
            raise ValueError(
                "Every condition must participate in a declared comparison."
            )
        return self


class CampaignExecution(StudyModel):
    artifact_root: str
    ledger: str
    order_seed: int = 20261110
    max_parallel_trials: int = Field(default=1, ge=1, le=8)
    max_attempts_per_trial: int = Field(default=2, ge=1, le=10)
    trial_timeout_seconds: int = Field(default=7200, ge=1)
    verification_timeout_seconds: int = Field(default=2400, ge=1)
    require_complete_blocks: bool = True
    repair: ToolExecutionConfig = Field(default_factory=ToolExecutionConfig)
    verification: VerificationConfig = Field(default_factory=VerificationConfig)


class StudyCampaign(StudyModel):
    schema_version: Literal[1] = 1
    campaign_id: Identifier
    mode: Literal["exploratory", "confirmatory"] = "exploratory"
    config_root: str = "."
    subjects_registry: str
    planned_runs_registry: str | None = None
    available_models: str = "available_models.yaml"
    runtime_profile: str = "swe_mcp_config.yaml"
    model: StudyModelProfile
    execution: CampaignExecution
    cohorts: dict[Identifier, CohortSpec]
    studies: list[StudySpec] = Field(min_length=1)

    @model_validator(mode="after")
    def study_references(self) -> StudyCampaign:
        ids = [study.id for study in self.studies]
        if len(ids) != len(set(ids)):
            raise ValueError("Study IDs must be unique.")
        if not {study.cohort for study in self.studies} <= set(self.cohorts):
            raise ValueError("A study references an unknown cohort.")
        if self.mode == "confirmatory" and self.model.provider == "CopilotSDK":
            raise ValueError(
                "The current confirmatory protocol requires controls not supported by CopilotSDK."
            )
        if self.mode == "confirmatory" and (
            self.model.seed is None or self.model.temperature is None
        ):
            raise ValueError(
                "Confirmatory campaigns require explicitly registered sampling controls."
            )
        return self
