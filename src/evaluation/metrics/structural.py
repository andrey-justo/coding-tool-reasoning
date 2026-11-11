from __future__ import annotations

import hashlib
import json
import math

from src.models.structural_metrics import (
    AnalyzerReport,
    StructuralComparison,
    StructuralComponentScales,
    StructuralMetricInput,
    StructuralProtocol,
    StructuralScore,
    StructuralWeights,
)

_COMPONENTS = ("solid", "arch", "smell")
_SEVERITY_WEIGHTS = {"minor": 1, "major": 3, "critical": 5}


def canonical_hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def source_hash(source: str) -> str:
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def _validate_pair(inputs: StructuralMetricInput) -> None:
    expected = {rule.instrument for rule in inputs.protocol.rules}
    for reports in (inputs.before, inputs.after):
        names = [report.instrument for report in reports]
        if len(names) != len(set(names)) or set(names) != expected:
            raise ValueError(
                "Reports must cover each registered instrument exactly once."
            )
        inventory = {file.path: (file.sha256, file.loc) for file in reports[0].files}
        for report in reports:
            rules = {
                rule.rule_id
                for rule in inputs.protocol.rules
                if rule.instrument == report.instrument
            }
            if set(report.analyzed_rules) != rules:
                raise ValueError(
                    "Analyzed rules must exactly match the registered mapping."
                )
            if {f.path: (f.sha256, f.loc) for f in report.files} != inventory:
                raise ValueError(
                    "Instruments must analyze the same source scope and LOC."
                )
            if report.loc_method != reports[0].loc_method:
                raise ValueError("Instruments must use the same LOC counting method.")

    before = {report.instrument: report for report in inputs.before}
    for after in inputs.after:
        baseline = before[after.instrument]
        if after.timestamp < baseline.timestamp:
            raise ValueError("After-analysis timestamp precedes the baseline analysis.")
        for field in (
            "instrument_version",
            "instrument_details",
            "ruleset_id",
            "ruleset_version",
            "configuration_sha256",
            "loc_method",
        ):
            if getattr(baseline, field) != getattr(after, field):
                raise ValueError(
                    f"Incomparable analyzer {after.instrument}: {field} changed."
                )
        if {f.path for f in baseline.files} != {f.path for f in after.files}:
            raise ValueError(
                "Before and after must analyze exactly the same target paths."
            )


def _normalize_components(
    densities: dict[str, float], scales: StructuralComponentScales
) -> dict[str, float]:
    normalized = {}
    for component, density in densities.items():
        scale = getattr(scales, component, None)
        if scale is None:
            raise ValueError(f"Missing registered reference scale for {component}.")
        # Equivalent to x / (x + scale), without overflowing the sum.
        ratio = density / scale if density <= scale else scale / density
        normalized[component] = (
            ratio / (1 + ratio) if density <= scale else 1 / (1 + ratio)
        )
    return normalized


def _composite(components: dict[str, float], weights: StructuralWeights) -> float:
    return math.fsum(
        getattr(weights, key) * components[key] for key in _COMPONENTS
    ) / math.fsum(getattr(weights, key) for key in _COMPONENTS)


def _score(
    reports: list[AnalyzerReport], protocol: StructuralProtocol
) -> StructuralScore:
    components = (
        (*_COMPONENTS, "reliability") if protocol.reliability_focus else _COMPONENTS
    )
    raw = dict.fromkeys(components, 0)
    weighted = dict.fromkeys(components, 0)
    rules = {(r.instrument, r.rule_id): r for r in protocol.rules}
    for report in reports:
        for finding in report.counts:
            rule = rules[(report.instrument, finding.rule_id)]
            if rule.component == "excluded":
                continue
            raw[rule.component] += finding.count
            weighted[rule.component] += finding.count * _SEVERITY_WEIGHTS[rule.severity]
    loc = sum(file.loc for file in reports[0].files)
    denominator = max(1.0, loc / 1000)
    densities = {key: weighted[key] / denominator for key in components}
    normalized = _normalize_components(densities, protocol.normalization.kloc)
    return StructuralScore(
        loc=loc,
        kloc=loc / 1000,
        normalization_denominator=denominator,
        raw_counts=raw,
        severity_weighted_counts=weighted,
        densities=densities,
        normalized_components=normalized,
        raw_v_struct=sum(
            getattr(protocol.weights, key) * densities[key] for key in _COMPONENTS
        ),
        v_struct=_composite(normalized, protocol.weights),
    )


def _deltas(before: float, after: float) -> dict[str, float]:
    return {
        "before": before,
        "after": after,
        "delta_struct": (before - after) / before
        if before > 0
        else (0.0 if after == 0 else -1.0),
        "delta_abs": after - before,
    }


def compare_structural_metrics(inputs: StructuralMetricInput) -> StructuralComparison:
    _validate_pair(inputs)
    before = _score(inputs.before, inputs.protocol)
    after = _score(inputs.after, inputs.protocol)
    delta = _deltas(before.v_struct, after.v_struct)
    tolerance = inputs.protocol.regression_tolerance
    absolute = delta["delta_abs"]
    verdict = (
        "neutral"
        if abs(absolute) <= tolerance
        else ("improved" if absolute < 0 else "regressed")
    )
    unweighted = [
        _composite(
            _normalize_components(
                {
                    c: score.raw_counts[c] / score.normalization_denominator
                    for c in _COMPONENTS
                },
                inputs.protocol.normalization.unweighted_severity,
            ),
            inputs.protocol.weights,
        )
        for score in (before, after)
    ]
    per_file = [
        _composite(
            _normalize_components(
                {
                    c: score.severity_weighted_counts[c] / len(reports[0].files)
                    for c in _COMPONENTS
                },
                inputs.protocol.normalization.per_file,
            ),
            inputs.protocol.weights,
        )
        for score, reports in ((before, inputs.before), (after, inputs.after))
    ]
    sensitivity = {
        "unweighted_severity": _deltas(*unweighted),
        "per_file": _deltas(*per_file),
    }
    if inputs.protocol.reliability_focus:
        sensitivity["reliability_substitution"] = _deltas(
            *[
                _composite(
                    {
                        **score.normalized_components,
                        "smell": score.normalized_components["reliability"],
                    },
                    inputs.protocol.weights,
                )
                for score in (before, after)
            ]
        )
    return StructuralComparison(
        before=before,
        after=after,
        delta_struct=delta["delta_struct"],
        delta_abs=absolute,
        effectiveness_verdict=verdict,
        rationale=(
            f"M-1 {inputs.protocol.metric_version} (bounded [0,1], "
            f"{inputs.protocol.normalization.method}): "
            f"V_before={before.v_struct:g}, V_after={after.v_struct:g}; "
            f"after-before={absolute:g}, registered absolute tolerance={tolerance:g}. "
            "This structural result does not establish passing builds or tests."
        ),
        protocol_sha256=canonical_hash(inputs.protocol.model_dump(mode="json")),
        evidence=inputs,
        sensitivity=sensitivity,
    )


def validate_metric_sources(
    inputs: StructuralMetricInput,
    before: dict[str, str],
    after: dict[str, str],
) -> None:
    for reports, sources in ((inputs.before, before), (inputs.after, after)):
        expected = {path: source_hash(code) for path, code in sources.items()}
        for report in reports:
            if {file.path: file.sha256 for file in report.files} != expected:
                raise ValueError(
                    "Analyzer evidence does not match the evaluated source snapshot."
                )
