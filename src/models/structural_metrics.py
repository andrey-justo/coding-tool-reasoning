from __future__ import annotations

import math
from datetime import datetime
from pathlib import PurePosixPath
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Component = Literal["solid", "arch", "smell"]
MeasuredComponent = Literal["solid", "arch", "smell", "reliability"]
Severity = Literal["minor", "major", "critical"]
NonEmpty = Annotated[str, Field(min_length=1)]
UnitInterval = Annotated[float, Field(ge=0, le=1)]


class MetricModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class StructuralWeights(MetricModel):
    solid: float = Field(default=0.50, ge=0, le=1)
    arch: float = Field(default=0.30, ge=0, le=1)
    smell: float = Field(default=0.20, ge=0, le=1)

    @model_validator(mode="after")
    def normalized(self) -> StructuralWeights:
        if not math.isclose(
            self.solid + self.arch + self.smell, 1, rel_tol=0, abs_tol=1e-12
        ):
            raise ValueError("Structural component weights must sum to one.")
        return self


class StructuralRule(MetricModel):
    instrument: NonEmpty
    rule_id: NonEmpty
    component: MeasuredComponent | Literal["excluded"]
    severity: Severity
    unit: Literal["occurrences", "lines"] = "occurrences"
    rationale: NonEmpty


class StructuralComponentScales(MetricModel):
    solid: float = Field(gt=0, strict=True)
    arch: float = Field(gt=0, strict=True)
    smell: float = Field(gt=0, strict=True)


class StructuralPrimaryScales(StructuralComponentScales):
    reliability: float | None = Field(default=None, gt=0, strict=True)


class StructuralNormalization(MetricModel):
    method: Literal["bounded-component-v1"] = "bounded-component-v1"
    kloc: StructuralPrimaryScales
    unweighted_severity: StructuralComponentScales
    per_file: StructuralComponentScales


class StructuralProtocol(MetricModel):
    metric_version: Literal["m1-bounded-v2"] = "m1-bounded-v2"
    protocol_id: NonEmpty
    mapping_version: NonEmpty
    weights: StructuralWeights = Field(default_factory=StructuralWeights)
    normalization: StructuralNormalization
    rules: list[StructuralRule] = Field(min_length=1)
    regression_tolerance: UnitInterval = 0
    reliability_focus: bool = False

    @model_validator(mode="after")
    def complete_mapping(self) -> StructuralProtocol:
        keys = [(rule.instrument, rule.rule_id) for rule in self.rules]
        if len(set(keys)) != len(keys):
            raise ValueError("Each instrument/rule must have exactly one mapping.")
        if not {"solid", "arch", "smell"} <= {r.component for r in self.rules}:
            raise ValueError("The protocol must map all three structural components.")
        if self.reliability_focus != any(
            r.component == "reliability" for r in self.rules
        ):
            raise ValueError(
                "Reliability sensitivity requires explicit task focus and registered reliability rules."
            )
        if self.reliability_focus != (self.normalization.kloc.reliability is not None):
            raise ValueError(
                "A reliability reference scale must be registered exactly when reliability focus is enabled."
            )
        return self


class AnalyzedFile(MetricModel):
    path: NonEmpty
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    loc: int = Field(ge=0, strict=True)

    @model_validator(mode="after")
    def relative_path(self) -> AnalyzedFile:
        path = PurePosixPath(self.path)
        if (
            "\\" in self.path
            or ":" in self.path
            or path.is_absolute()
            or ".." in path.parts
            or str(path) != self.path
            or self.path == "."
        ):
            raise ValueError(
                "Metric paths must be canonical repository-relative paths."
            )
        return self


class RuleCount(MetricModel):
    rule_id: NonEmpty
    path: NonEmpty
    count: int = Field(ge=0, strict=True)


class AnalyzerReport(MetricModel):
    instrument: NonEmpty
    instrument_version: NonEmpty
    instrument_details: dict[str, str] = Field(default_factory=dict)
    ruleset_id: NonEmpty
    ruleset_version: NonEmpty
    configuration_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    timestamp: datetime
    loc_method: NonEmpty
    source: NonEmpty
    files: list[AnalyzedFile] = Field(min_length=1)
    analyzed_rules: list[NonEmpty] = Field(min_length=1)
    counts: list[RuleCount] = Field(default_factory=list)

    @model_validator(mode="after")
    def complete_report(self) -> AnalyzerReport:
        if self.timestamp.tzinfo is None or self.timestamp.utcoffset() is None:
            raise ValueError("Analyzer timestamps must include a timezone.")
        paths = [file.path for file in self.files]
        if len(paths) != len(set(paths)):
            raise ValueError("Analyzer report contains duplicate files.")
        if len(self.analyzed_rules) != len(set(self.analyzed_rules)):
            raise ValueError("Analyzer report contains duplicate analyzed rules.")
        keys = [(count.rule_id, count.path) for count in self.counts]
        if len(keys) != len(set(keys)):
            raise ValueError("Aggregate counts must be unique by rule and file.")
        for count in self.counts:
            if count.path not in paths or count.rule_id not in self.analyzed_rules:
                raise ValueError("A finding is outside the analyzed files or rules.")
        return self


class StructuralMetricInput(MetricModel):
    protocol: StructuralProtocol
    before: list[AnalyzerReport] = Field(min_length=1)
    after: list[AnalyzerReport] = Field(min_length=1)


class StructuralScore(MetricModel):
    loc: int
    kloc: float
    normalization_denominator: float
    raw_counts: dict[MeasuredComponent, int]
    severity_weighted_counts: dict[MeasuredComponent, int]
    densities: dict[MeasuredComponent, float]
    normalized_components: dict[MeasuredComponent, UnitInterval]
    raw_v_struct: float = Field(ge=0)
    v_struct: UnitInterval


class StructuralComparison(MetricModel):
    before: StructuralScore
    after: StructuralScore
    delta_struct: float
    delta_abs: float
    effectiveness_verdict: Literal["improved", "neutral", "regressed"]
    rationale: str
    protocol_sha256: str
    evidence: StructuralMetricInput
    sensitivity: dict[str, dict[str, float]]
