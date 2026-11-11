from __future__ import annotations

from copy import deepcopy

import pytest
from pydantic import ValidationError

from src.evaluation.metrics.structural import (
    _normalize_components,
    compare_structural_metrics,
    source_hash,
    validate_metric_sources,
)
from src.models.code_gen_plan import CodeGenPlan
from src.models.structural_metrics import (
    AnalyzerReport,
    StructuralComparison,
    StructuralComponentScales,
    StructuralMetricInput,
    StructuralProtocol,
    StructuralWeights,
)
from src.models.swe_context import SweContext
from src.service.explanation_service import ExplanationService


def synthetic_protocol() -> dict:
    """Arithmetic fixtures, not a validated production SOLID rule mapping."""
    return {
        "protocol_id": "synthetic-tests-only",
        "mapping_version": "1",
        "normalization": {
            "kloc": {"solid": 6, "arch": 5, "smell": 3},
            "unweighted_severity": {"solid": 2, "arch": 1, "smell": 3},
            "per_file": {"solid": 12, "arch": 10, "smell": 6},
        },
        "rules": [
            {
                "instrument": "fixture",
                "rule_id": rule,
                "component": component,
                "severity": severity,
                "rationale": "Synthetic arithmetic fixture only.",
            }
            for rule, component, severity in (
                ("S", "solid", "major"),
                ("A", "arch", "critical"),
                ("M", "smell", "minor"),
            )
        ],
    }


def synthetic_report(counts=(4, 2, 6), loc=2000, source="before") -> dict:
    return {
        "instrument": "fixture",
        "instrument_version": "1",
        "ruleset_id": "synthetic",
        "ruleset_version": "1",
        "configuration_sha256": "a" * 64,
        "timestamp": "2026-01-01T00:00:00Z",
        "loc_method": "fixture-loc-v1",
        "source": "synthetic-test-report",
        "files": [{"path": "a.py", "sha256": source_hash(source), "loc": loc}],
        "analyzed_rules": ["S", "A", "M"],
        "counts": [
            {"rule_id": rule, "path": "a.py", "count": count}
            for rule, count in zip(("S", "A", "M"), counts, strict=True)
        ],
    }


def synthetic_input(
    before=(4, 2, 6), after=(2, 1, 3), loc=2000
) -> StructuralMetricInput:
    return StructuralMetricInput.model_validate(
        {
            "protocol": synthetic_protocol(),
            "before": [synthetic_report(before, loc, "before")],
            "after": [synthetic_report(after, loc, "after")],
        }
    )


def test_exact_registered_formula_and_audit_evidence():
    inputs = synthetic_input()
    result = compare_structural_metrics(inputs)
    assert result.before.raw_counts == {"solid": 4, "arch": 2, "smell": 6}
    assert result.before.severity_weighted_counts == {
        "solid": 12,
        "arch": 10,
        "smell": 6,
    }
    assert result.before.densities == {"solid": 6, "arch": 5, "smell": 3}
    assert result.before.raw_v_struct == pytest.approx(5.1)
    assert result.after.raw_v_struct == pytest.approx(2.55)
    assert result.before.normalized_components == {
        "solid": 0.5,
        "arch": 0.5,
        "smell": 0.5,
    }
    assert result.before.v_struct == pytest.approx(0.5)
    assert result.after.v_struct == pytest.approx(1 / 3)
    assert result.delta_struct == pytest.approx(1 / 3)
    assert result.delta_abs == pytest.approx(-1 / 6)
    assert result.effectiveness_verdict == "improved"
    assert result.evidence == inputs
    assert len(result.protocol_sha256) == 64
    assert result.sensitivity["unweighted_severity"]["before"] == pytest.approx(0.5)
    assert result.sensitivity["per_file"]["before"] == pytest.approx(0.5)
    assert result.model_dump(mode="json")["evidence"]["before"][0][
        "timestamp"
    ].endswith("Z")


@pytest.mark.parametrize(
    "loc,denominator", [(0, 1), (100, 1), (999, 1), (1000, 1), (1500, 1.5), (3000, 3)]
)
def test_exact_kloc_floor(loc, denominator):
    result = compare_structural_metrics(synthetic_input(loc=loc))
    assert result.before.normalization_denominator == denominator
    assert result.before.raw_v_struct == pytest.approx(10.2 / denominator)
    assert result.before.v_struct == pytest.approx(2 / (2 + denominator))


@pytest.mark.parametrize(
    "before,after,delta,verdict",
    [
        ((0, 0, 0), (0, 0, 0), 0, "neutral"),
        ((0, 0, 0), (1, 0, 0), -1, "regressed"),
        ((1, 0, 0), (4, 0, 0), -1.5, "regressed"),
        ((1, 0, 0), (0, 0, 0), 1, "improved"),
    ],
)
def test_zero_baseline_and_unbounded_negative_delta(before, after, delta, verdict):
    result = compare_structural_metrics(synthetic_input(before, after))
    assert result.delta_struct == pytest.approx(delta)
    assert result.effectiveness_verdict == verdict


def test_each_snapshot_uses_its_own_loc():
    data = synthetic_input().model_dump(mode="json")
    data["after"][0]["files"][0]["loc"] = 1000
    result = compare_structural_metrics(StructuralMetricInput.model_validate(data))
    assert result.delta_struct == 0


@pytest.mark.parametrize(
    "weights",
    [
        {"solid": -0.1, "arch": 0.9, "smell": 0.2},
        {"solid": 0.5, "arch": 0.5, "smell": 0.2},
        {"solid": float("nan")},
        {"solid": float("inf")},
    ],
)
def test_invalid_weights_are_rejected(weights):
    with pytest.raises(ValidationError):
        StructuralWeights.model_validate(weights)


def test_omitted_weights_use_defaults_and_match_explicit_default_registration():
    omitted = synthetic_input()
    assert omitted.protocol.weights.model_dump() == {
        "solid": 0.50, "arch": 0.30, "smell": 0.20,
    }
    data = omitted.model_dump(mode="json")
    del data["protocol"]["weights"]
    implicit = compare_structural_metrics(StructuralMetricInput.model_validate(data))
    explicit = compare_structural_metrics(omitted)
    assert implicit == explicit


@pytest.mark.parametrize("weights,expected", [
    ({"solid": 0.60, "arch": 0.25, "smell": 0.15}, 0.30),
    ({"solid": 1.0, "arch": 0.0, "smell": 0.0}, 0.50),
])
def test_configured_weights_drive_primary_and_sensitivity_scores(weights, expected):
    data = synthetic_input(before=(4, 0, 0), after=(0, 0, 0)).model_dump(mode="json")
    original = compare_structural_metrics(StructuralMetricInput.model_validate(data))
    data["protocol"]["weights"] = weights
    result = compare_structural_metrics(StructuralMetricInput.model_validate(data))
    assert result.before.v_struct == pytest.approx(expected)
    assert result.before.v_struct != original.before.v_struct
    assert result.protocol_sha256 != original.protocol_sha256
    assert result.evidence.protocol.weights.model_dump() == weights
    for sensitivity in result.sensitivity.values():
        assert sensitivity["before"] == pytest.approx(expected)
        assert sensitivity["after"] == 0
    assert 0 <= result.before.v_struct <= 1


@pytest.mark.parametrize(
    "field,value",
    [
        ("instrument_version", "2"),
        ("ruleset_id", "other"),
        ("ruleset_version", "2"),
        ("configuration_sha256", "b" * 64),
        ("loc_method", "different-loc"),
        ("timestamp", "2025-01-01T00:00:00Z"),
    ],
)
def test_incomparable_instruments_fail(field, value):
    data = synthetic_input().model_dump(mode="json")
    data["after"][0][field] = value
    with pytest.raises(ValueError):
        compare_structural_metrics(StructuralMetricInput.model_validate(data))


def test_scope_and_rule_coverage_are_not_silently_relaxed():
    data = synthetic_input().model_dump(mode="json")
    data["after"][0]["files"][0]["path"] = "b.py"
    for count in data["after"][0]["counts"]:
        count["path"] = "b.py"
    with pytest.raises(ValueError, match="same target paths"):
        compare_structural_metrics(StructuralMetricInput.model_validate(data))
    data = synthetic_input().model_dump(mode="json")
    data["after"][0]["analyzed_rules"].append("UNREGISTERED")
    with pytest.raises(ValueError, match="registered mapping"):
        compare_structural_metrics(StructuralMetricInput.model_validate(data))


@pytest.mark.parametrize(
    "change", ["duplicate-rule", "missing-component", "unregistered-reliability"]
)
def test_invalid_protocols_fail(change):
    data = synthetic_protocol()
    if change == "duplicate-rule":
        data["rules"].append(deepcopy(data["rules"][0]))
    elif change == "missing-component":
        data["rules"].pop()
    else:
        data["reliability_focus"] = True
    with pytest.raises(ValidationError):
        StructuralProtocol.model_validate(data)


@pytest.mark.parametrize(
    "change",
    [
        "duplicate-file",
        "duplicate-count",
        "negative",
        "fractional",
        "bool",
        "naive-time",
        "unmapped-count",
        "traversal",
    ],
)
def test_invalid_reports_fail(change):
    data = synthetic_report()
    if change == "duplicate-file":
        data["files"].append(deepcopy(data["files"][0]))
    elif change == "duplicate-count":
        data["counts"].append(deepcopy(data["counts"][0]))
    elif change in {"negative", "fractional", "bool"}:
        data["counts"][0]["count"] = {"negative": -1, "fractional": 0.5, "bool": True}[
            change
        ]
    elif change == "naive-time":
        data["timestamp"] = "2026-01-01T00:00:00"
    elif change == "unmapped-count":
        data["counts"][0]["rule_id"] = "unknown"
    else:
        data["files"][0]["path"] = "../a.py"
    with pytest.raises(ValidationError):
        AnalyzerReport.model_validate(data)


def test_snapshot_provenance_must_match_exact_evaluated_sources():
    inputs = synthetic_input()
    validate_metric_sources(inputs, {"a.py": "before"}, {"a.py": "after"})
    with pytest.raises(ValueError, match="source snapshot"):
        validate_metric_sources(inputs, {"a.py": "before"}, {"a.py": "stale"})


def test_missing_and_duplicate_instrument_reports_fail():
    data = synthetic_input().model_dump(mode="json")
    data["before"].append(deepcopy(data["before"][0]))
    with pytest.raises(ValueError, match="exactly once"):
        compare_structural_metrics(StructuralMetricInput.model_validate(data))


def test_multiple_instruments_must_agree_on_sources_and_loc():
    data = synthetic_input().model_dump(mode="json")
    for rule in deepcopy(data["protocol"]["rules"]):
        rule["instrument"] = "other"
        data["protocol"]["rules"].append(rule)
    for stage in ("before", "after"):
        report = deepcopy(data[stage][0])
        report["instrument"] = "other"
        data[stage].append(report)
    compare_structural_metrics(StructuralMetricInput.model_validate(data))
    data["after"][1]["files"][0]["loc"] += 1
    with pytest.raises(ValueError, match="same source scope and LOC"):
        compare_structural_metrics(StructuralMetricInput.model_validate(data))


def test_registered_tolerance_does_not_change_raw_delta():
    data = synthetic_input().model_dump(mode="json")
    data["protocol"]["regression_tolerance"] = 0.2
    result = compare_structural_metrics(StructuralMetricInput.model_validate(data))
    assert result.effectiveness_verdict == "neutral"
    assert result.delta_abs == pytest.approx(-1 / 6)


def test_reliability_sensitivity_is_separate_from_primary_measure():
    data = synthetic_input().model_dump(mode="json")
    data["protocol"]["reliability_focus"] = True
    data["protocol"]["normalization"]["kloc"]["reliability"] = 3
    data["protocol"]["rules"].append(
        {
            **data["protocol"]["rules"][2],
            "rule_id": "R",
            "component": "reliability",
        }
    )
    for stage, count in (("before", 9), ("after", 0)):
        data[stage][0]["analyzed_rules"].append("R")
        data[stage][0]["counts"].append(
            {"rule_id": "R", "path": "a.py", "count": count}
        )
    result = compare_structural_metrics(StructuralMetricInput.model_validate(data))
    assert result.before.v_struct == pytest.approx(0.5)
    assert result.sensitivity["reliability_substitution"]["before"] == pytest.approx(
        0.52
    )
    assert 0 <= result.sensitivity["reliability_substitution"]["after"] <= 1


@pytest.mark.parametrize(
    "response",
    [
        '{"overall_verdict":"acceptable","rationale":"ok","nfr_impacts":[],"risks":[],"recommended_tests":[]}',
        "invalid-json",
    ],
)
def test_judge_attaches_objective_evidence_even_when_llm_judgment_fails(response):
    class KB:
        def find_nfr_ids(self, focus):
            return []

        def summarize_for_prompt(self, *args, **kwargs):
            return ""

    class LLM:
        def chat(self, prompt):
            return response

    service = ExplanationService(kb=KB(), llm_client=LLM())
    context = SweContext(
        plan=CodeGenPlan(problem_description="Improve code"), swe_summary=""
    )
    result = service.explain_change(
        context,
        "before",
        "after",
        structural_metrics=synthetic_input(),
    )
    assert result.objective_metrics.delta_struct == pytest.approx(1 / 3)
    assert result.effectiveness_verdict == "improved"
    if response == "invalid-json":
        assert result.overall_verdict == "manual-review-required"
    with pytest.raises(ValueError, match="source snapshot"):
        service.explain_change(
            context,
            "before",
            "not-the-analyzed-code",
            structural_metrics=synthetic_input(),
        )


@pytest.mark.parametrize("profile", ["kloc", "unweighted_severity", "per_file"])
@pytest.mark.parametrize("invalid", [0, -1, float("nan"), float("inf"), True, "6"])
def test_normalization_requires_positive_finite_explicit_scales(profile, invalid):
    data = synthetic_protocol()
    data["normalization"][profile]["solid"] = invalid
    with pytest.raises(ValidationError):
        StructuralProtocol.model_validate(data)


@pytest.mark.parametrize("profile", ["kloc", "unweighted_severity", "per_file"])
def test_each_normalization_profile_must_cover_all_components(profile):
    data = synthetic_protocol()
    del data["normalization"][profile]["smell"]
    with pytest.raises(ValidationError):
        StructuralProtocol.model_validate(data)


def test_legacy_protocol_requires_explicit_normalization_before_recomputation():
    data = synthetic_protocol()
    del data["normalization"]
    with pytest.raises(ValidationError, match="normalization"):
        StructuralProtocol.model_validate(data)


def test_normalization_cannot_be_fitted_separately_to_each_snapshot():
    inputs = synthetic_input(after=(200000, 100000, 300000))
    result = compare_structural_metrics(inputs)
    assert result.before.v_struct == 0.5
    assert result.before.normalized_components == {
        "solid": 0.5,
        "arch": 0.5,
        "smell": 0.5,
    }
    assert result.after.v_struct > 0.99
    assert result.delta_struct < 0
    assert inputs.protocol.metric_version == "m1-bounded-v2"
    assert result.evidence.protocol.normalization.kloc.solid == 6


@pytest.mark.parametrize("counts", [(0, 0, 0), (1, 1, 1), (10**12, 10**12, 10**12)])
def test_primary_components_and_all_sensitivity_scores_are_bounded(counts):
    result = compare_structural_metrics(synthetic_input(before=counts))
    for score in (result.before, result.after):
        assert 0 <= score.v_struct <= 1
        assert all(0 <= value <= 1 for value in score.normalized_components.values())
    for sensitivity in result.sensitivity.values():
        assert 0 <= sensitivity["before"] <= 1
        assert 0 <= sensitivity["after"] <= 1


def test_high_volume_smells_cannot_exceed_their_weighted_contribution():
    result = compare_structural_metrics(synthetic_input(before=(0, 0, 10**12)))
    assert result.before.densities["smell"] > 10**10
    assert result.before.raw_v_struct > 10**10
    assert 0 < result.before.v_struct <= 0.20
    assert result.before.normalized_components["solid"] == 0
    assert result.before.normalized_components["arch"] == 0


def test_reference_scales_are_in_protocol_hash_and_raw_evidence_is_preserved():
    data = synthetic_input().model_dump(mode="json")
    original = compare_structural_metrics(StructuralMetricInput.model_validate(data))
    data["protocol"]["normalization"]["kloc"]["solid"] = 12
    changed = compare_structural_metrics(StructuralMetricInput.model_validate(data))
    assert changed.protocol_sha256 != original.protocol_sha256
    assert changed.before.v_struct < original.before.v_struct
    assert changed.before.densities == original.before.densities
    assert changed.before.raw_v_struct == original.before.raw_v_struct
    assert changed.before.raw_counts == original.before.raw_counts


def test_bounded_transform_is_stable_for_large_finite_density_and_scale():
    data = synthetic_input(before=(10**307, 10**307, 10**307)).model_dump(mode="json")
    data["protocol"]["normalization"]["kloc"] = {
        "solid": 1.5e307,
        "arch": 2.5e307,
        "smell": 5e306,
    }
    result = compare_structural_metrics(StructuralMetricInput.model_validate(data))
    assert result.before.v_struct == pytest.approx(0.5)
    assert result.before.raw_v_struct > 1e306
    scales = StructuralComponentScales(solid=1e308, arch=1, smell=1)
    assert _normalize_components({"solid": 1e308, "arch": 0, "smell": 0}, scales) == {
        "solid": 0.5,
        "arch": 0.0,
        "smell": 0.0,
    }


def test_bounded_composite_handles_accepted_weight_roundoff_at_upper_bound():
    data = synthetic_input(before=(10**100, 10**100, 10**100)).model_dump(mode="json")
    data["protocol"]["weights"]["smell"] = 0.20000000000001
    result = compare_structural_metrics(StructuralMetricInput.model_validate(data))
    assert result.before.v_struct == 1


def test_independent_sensitivity_reference_scales_are_applied():
    data = synthetic_input().model_dump(mode="json")
    data["protocol"]["normalization"]["per_file"] = {
        "solid": 24,
        "arch": 20,
        "smell": 12,
    }
    data["protocol"]["normalization"]["unweighted_severity"] = {
        "solid": 4,
        "arch": 2,
        "smell": 6,
    }
    result = compare_structural_metrics(StructuralMetricInput.model_validate(data))
    assert result.before.v_struct == 0.5
    assert result.sensitivity["per_file"]["before"] == pytest.approx(1 / 3)
    assert result.sensitivity["unweighted_severity"]["before"] == pytest.approx(1 / 3)


def test_reliability_scale_is_required_only_for_the_registered_substitution():
    data = synthetic_protocol()
    data["normalization"]["kloc"]["reliability"] = 3
    with pytest.raises(ValidationError, match="reliability reference scale"):
        StructuralProtocol.model_validate(data)
    for profile in ("unweighted_severity", "per_file"):
        data = synthetic_protocol()
        data["normalization"][profile]["reliability"] = 3
        with pytest.raises(ValidationError, match="Extra inputs"):
            StructuralProtocol.model_validate(data)


@pytest.mark.parametrize("field", ["v_struct", "normalized_components"])
def test_score_schema_rejects_out_of_range_normalized_values(field):
    data = compare_structural_metrics(synthetic_input()).model_dump(mode="json")
    if field == "v_struct":
        data["before"][field] = 1.01
    else:
        data["before"][field]["solid"] = -0.01
    with pytest.raises(ValidationError):
        StructuralComparison.model_validate(data)
