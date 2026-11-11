from __future__ import annotations

from src.models.structural_metrics import StructuralMetricInput
from src.models.swe_context import SweContext
from src.models.swe_explanation import SweCodeChangeExplanation
from src.service.explanation_service import ExplanationService


class JudgeSweCodeChangeTool:
    """Class-based judge tool for easier mocking and unit testing."""

    def __init__(self, registry) -> None:
        self._registry = registry

    def execute(
        self,
        swe_context: SweContext,
        original_code: str,
        modified_code: str,
        structural_metrics: StructuralMetricInput | None = None,
    ) -> SweCodeChangeExplanation:
        """Stage 2 – judge and explain a code change."""

        ctx = self._registry._create_swe_server_context()
        kb = ctx.kb
        service_cls = self._registry._explanation_service_cls or ExplanationService
        service = service_cls(kb=kb, config=ctx.config)

        kwargs = {}
        if structural_metrics is not None:
            kwargs["structural_metrics"] = structural_metrics
        return service.explain_change(
            swe_context=swe_context,
            original_code=original_code,
            modified_code=modified_code,
            **kwargs,
        )
