from pathlib import Path

from src.evaluation.experiment_metrics import ExperimentMetricsEvaluator


class _FakeLLMClient:
    def __init__(self, response: str):
        self._response = response

    def chat(self, prompt, model=None):
        return self._response


def test_cyclomatic_complexity_increases_with_control_flow():
    evaluator = ExperimentMetricsEvaluator()
    code = """
def f(x):
    if x > 0:
        return 1
    elif x == 0:
        return 0
    return -1
"""
    assert evaluator.cyclomatic_complexity(code) >= 3


def test_cognitive_complexity_penalizes_nesting():
    evaluator = ExperimentMetricsEvaluator()
    flat_code = """
def f(x):
    if x > 0:
        return x
    return 0
"""
    nested_code = """
def f(x, y):
    if x > 0:
        if y > 0:
            return x + y
    return 0
"""
    assert evaluator.cognitive_complexity(nested_code) > evaluator.cognitive_complexity(
        flat_code
    )


def test_requirements_coverage_reports_matches():
    evaluator = ExperimentMetricsEvaluator()
    requirements = [
        "Add retry mechanism for transient failures",
        "Expose request timeout configuration",
    ]
    artifact = "Implemented retry policy with backoff and max retries."

    result = evaluator.requirements_coverage(requirements, artifact)

    assert result["total"] == 2
    assert result["covered"] == 1
    assert result["matches"] == [True, False]


def test_test_pass_rate_from_counts():
    evaluator = ExperimentMetricsEvaluator()
    result = evaluator.test_pass_rate_from_counts(total=10, failures=2, errors=1)

    assert result.passed == 7
    assert result.total == 10
    assert result.pass_rate == 0.7


def test_test_pass_rate_from_junit_xml(tmp_path: Path):
    evaluator = ExperimentMetricsEvaluator()
    report = tmp_path / "junit.xml"
    report.write_text(
        """
<testsuites>
  <testsuite name=\"suite-a\" tests=\"5\" failures=\"1\" errors=\"0\" />
  <testsuite name=\"suite-b\" tests=\"3\" failures=\"0\" errors=\"1\" />
</testsuites>
""".strip(),
        encoding="utf-8",
    )

    result = evaluator.test_pass_rate_from_junit_xml(report)

    assert result.total == 8
    assert result.passed == 6
    assert result.pass_rate == 0.75


def test_buse_weimer_proxy_returns_normalized_score():
    evaluator = ExperimentMetricsEvaluator()
    code = """
# short comment

def add(a, b):
    return a + b
"""
    score = evaluator.buse_weimer_readability_proxy(code)
    assert 0.0 <= score <= 1.0


def test_llm_readability_evaluation_parses_json_payload():
    evaluator = ExperimentMetricsEvaluator()
    llm = _FakeLLMClient(
        '{"score": 0.82, "rationale": "Clear naming and simple flow."}'
    )

    evaluation = evaluator.llm_readability_evaluation(
        "def f():\n    return 1", llm_client=llm
    )

    assert evaluation.score == 0.82
    assert "Clear naming" in evaluation.rationale


def test_evaluate_all_returns_requested_metric_groups():
    evaluator = ExperimentMetricsEvaluator()
    llm = _FakeLLMClient('{"score": 0.5, "rationale": "ok"}')

    result = evaluator.evaluate_all(
        generated_code="def add(a, b):\n    return a + b",
        reference_code=None,
        requirements=["add two numbers"],
        artifacts="function add returns sum",
        test_total=4,
        test_failures=1,
        llm_client=llm,
    )

    assert "complexity" in result
    assert "intent_adherence" in result
    assert "readability" in result
    assert "design_quality" in result
    assert result["intent_adherence"]["test_pass_rate"]["rate"] == 0.75


def test_solid_violation_delta_handles_standard_and_zero_baseline_cases():
    evaluator = ExperimentMetricsEvaluator()

    improved = evaluator.solid_violation_delta(violations_before=10, violations_after=6)
    assert improved.delta == 0.4
    assert improved.absolute_delta == -4

    clean_kept_clean = evaluator.solid_violation_delta(
        violations_before=0, violations_after=0
    )
    assert clean_kept_clean.delta == 0.0
    assert clean_kept_clean.absolute_delta == 0

    clean_regressed = evaluator.solid_violation_delta(
        violations_before=0, violations_after=3
    )
    assert clean_regressed.delta == -1.0
    assert clean_regressed.absolute_delta == 3
