from __future__ import annotations

from pathlib import Path
from typing import Any, Optional, Sequence

from bert_score import BERTScorer

from src.evaluation.metrics import (
    ComplexityMetricsStrategy,
    IntentAdherenceMetricsStrategy,
    LLMEvaluation,
    ReadabilityMetricsStrategy,
    SolidDeltaResult,
    SolidMetricsStrategy,
    TestPassRate,
)


class ExperimentMetricsEvaluator:
    """Orchestrates metric strategies and returns grouped metric maps.

    Grouped outputs:
    - design_quality
    - complexity
    - intent_adherence
    - readability
    """

    def __init__(self, scorer: Optional[BERTScorer] = None) -> None:
        self._scorer = scorer
        self._complexity = ComplexityMetricsStrategy()
        self._intent = IntentAdherenceMetricsStrategy()
        self._readability = ReadabilityMetricsStrategy()
        self._solid = SolidMetricsStrategy()

    def _get_scorer(self) -> BERTScorer:
        if self._scorer is None:
            self._scorer = BERTScorer(
                model_type="microsoft/codebert-base",
                num_layers=12,
                lang="en",
            )
        return self._scorer

    # Compatibility wrappers for existing callers/tests.
    def cyclomatic_complexity(self, code: str) -> int:
        return self._complexity.cyclomatic_complexity(code)

    def cognitive_complexity(self, code: str) -> int:
        return self._complexity.cognitive_complexity(code)

    def semantic_similarity_codebert(
        self,
        generated_code: str,
        reference_code: str,
    ) -> dict[str, float]:
        return self._intent.semantic_similarity_codebert(
            generated_code=generated_code,
            reference_code=reference_code,
            scorer=self._get_scorer(),
        )

    def requirements_coverage(
        self,
        requirements: Sequence[str],
        artifacts: Sequence[str] | str,
    ) -> dict[str, Any]:
        return self._intent.requirements_coverage(requirements, artifacts)

    @staticmethod
    def test_pass_rate_from_counts(
        total: int, failures: int, errors: int = 0
    ) -> TestPassRate:
        return IntentAdherenceMetricsStrategy.test_pass_rate_from_counts(
            total, failures, errors
        )

    def test_pass_rate_from_junit_xml(self, xml_path: str | Path) -> TestPassRate:
        return self._intent.test_pass_rate_from_junit_xml(xml_path)

    def buse_weimer_readability_proxy(self, code: str) -> float:
        return self._readability.buse_weimer_readability_proxy(code)

    def llm_readability_evaluation(
        self,
        code: str,
        llm_client: Any,
        model: Optional[str] = None,
    ) -> LLMEvaluation:
        return self._readability.llm_readability_evaluation(code, llm_client, model)

    def solid_violation_delta(
        self,
        violations_before: int,
        violations_after: int,
    ) -> SolidDeltaResult:
        return self._solid.solid_violation_delta(violations_before, violations_after)

    def count_solid_violations_from_issues(
        self,
        issues: Sequence[dict[str, Any]],
        rule_keys: set[str] | None = None,
        severities: set[str] | None = None,
    ) -> int:
        return self._solid.count_violations_from_issues(issues, rule_keys, severities)

    def evaluate_all(
        self,
        generated_code: str,
        reference_code: Optional[str],
        requirements: Sequence[str],
        artifacts: Sequence[str] | str,
        test_total: Optional[int] = None,
        test_failures: Optional[int] = None,
        test_errors: int = 0,
        junit_xml_path: Optional[str | Path] = None,
        llm_client: Optional[Any] = None,
        llm_model: Optional[str] = None,
        solid_violations_before: Optional[int] = None,
        solid_violations_after: Optional[int] = None,
    ) -> dict[str, Any]:
        scorer = self._get_scorer() if reference_code else None

        return {
            "design_quality": {
                "solid_violation_delta": self._solid.compute(
                    violations_before=solid_violations_before,
                    violations_after=solid_violations_after,
                )
            },
            "complexity": self._complexity.compute(generated_code),
            "intent_adherence": self._intent.compute(
                generated_code=generated_code,
                reference_code=reference_code,
                requirements=requirements,
                artifacts=artifacts,
                scorer=scorer,
                test_total=test_total,
                test_failures=test_failures,
                test_errors=test_errors,
                junit_xml_path=junit_xml_path,
            ),
            "readability": self._readability.compute(
                code=generated_code,
                llm_client=llm_client,
                llm_model=llm_model,
            ),
        }
