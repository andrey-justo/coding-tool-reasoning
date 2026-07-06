from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable


@dataclass
class SolidDeltaResult:
    violations_before: int
    violations_after: int
    delta: float
    absolute_delta: int


class SolidMetricsStrategy:
    """SOLID violation metrics based on pre-counted static-analysis findings."""

    @staticmethod
    def solid_violation_delta(
        violations_before: int,
        violations_after: int,
    ) -> SolidDeltaResult:
        vb = max(0, int(violations_before))
        va = max(0, int(violations_after))

        if vb > 0:
            delta = (vb - va) / vb
        elif va == 0:
            delta = 0.0
        else:
            delta = -1.0

        return SolidDeltaResult(
            violations_before=vb,
            violations_after=va,
            delta=delta,
            absolute_delta=va - vb,
        )

    @staticmethod
    def count_violations_from_issues(
        issues: Iterable[dict[str, Any]],
        rule_keys: set[str] | None = None,
        severities: set[str] | None = None,
    ) -> int:
        count = 0
        for issue in issues:
            rule = str(issue.get("rule") or "")
            severity = str(issue.get("severity") or "").upper()

            if rule_keys and rule not in rule_keys:
                continue
            if severities and severity not in {value.upper() for value in severities}:
                continue
            count += 1
        return count

    def compute(
        self,
        violations_before: int | None,
        violations_after: int | None,
    ) -> dict[str, Any] | None:
        if violations_before is None or violations_after is None:
            return None

        result = self.solid_violation_delta(violations_before, violations_after)
        return {
            "violations_before": result.violations_before,
            "violations_after": result.violations_after,
            "delta": result.delta,
            "absolute_delta": result.absolute_delta,
        }
