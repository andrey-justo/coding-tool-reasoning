from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Sequence

_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "if",
    "in",
    "into",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "to",
    "with",
}


@dataclass
class TestPassRate:
    passed: int
    total: int
    pass_rate: float


class IntentAdherenceMetricsStrategy:
    """Intent adherence metrics (requirements, testability, semantic similarity)."""

    @staticmethod
    def _tokenize(text: str) -> set[str]:
        import re

        tokens = {
            token
            for token in re.findall(r"[a-zA-Z_][a-zA-Z0-9_]+", text.lower())
            if token not in _STOPWORDS and len(token) > 2
        }
        return tokens

    def requirements_coverage(
        self,
        requirements: Sequence[str],
        artifacts: Sequence[str] | str,
    ) -> dict[str, Any]:
        if not requirements:
            return {"covered": 0, "total": 0, "coverage": 0.0, "matches": []}

        if isinstance(artifacts, str):
            corpus = artifacts
        else:
            corpus = "\n".join(artifacts)

        corpus_tokens = self._tokenize(corpus)
        matches: list[bool] = []
        for req in requirements:
            req_tokens = self._tokenize(req)
            match = bool(req_tokens and req_tokens.intersection(corpus_tokens))
            matches.append(match)

        covered = sum(1 for matched in matches if matched)
        total = len(requirements)
        return {
            "covered": covered,
            "total": total,
            "coverage": covered / total if total else 0.0,
            "matches": matches,
        }

    @staticmethod
    def test_pass_rate_from_counts(
        total: int, failures: int, errors: int = 0
    ) -> TestPassRate:
        safe_total = max(total, 0)
        failed = max(failures, 0) + max(errors, 0)
        passed = max(safe_total - failed, 0)
        rate = (passed / safe_total) if safe_total else 0.0
        return TestPassRate(passed=passed, total=safe_total, pass_rate=rate)

    def test_pass_rate_from_junit_xml(self, xml_path: str | Path) -> TestPassRate:
        tree = ET.parse(str(xml_path))
        root = tree.getroot()

        total = 0
        failures = 0
        errors = 0

        for suite in root.iter("testsuite"):
            total += int(suite.attrib.get("tests", 0))
            failures += int(suite.attrib.get("failures", 0))
            errors += int(suite.attrib.get("errors", 0))

        return self.test_pass_rate_from_counts(
            total=total, failures=failures, errors=errors
        )

    def semantic_similarity_codebert(
        self,
        generated_code: str,
        reference_code: str,
        scorer: Any,
    ) -> dict[str, float]:
        precision, recall, f1 = scorer.score([generated_code], [reference_code])
        return {
            "precision": precision[0].item(),
            "recall": recall[0].item(),
            "f1": f1[0].item(),
        }

    def compute(
        self,
        generated_code: str,
        reference_code: Optional[str],
        requirements: Sequence[str],
        artifacts: Sequence[str] | str,
        scorer: Any | None,
        test_total: Optional[int] = None,
        test_failures: Optional[int] = None,
        test_errors: int = 0,
        junit_xml_path: Optional[str | Path] = None,
    ) -> dict[str, Any]:
        result: dict[str, Any] = {
            "requirements_coverage": self.requirements_coverage(
                requirements, artifacts
            ),
        }

        if reference_code and scorer is not None:
            result["semantic_similarity_codebert"] = self.semantic_similarity_codebert(
                generated_code,
                reference_code,
                scorer,
            )
        else:
            result["semantic_similarity_codebert"] = None

        if junit_xml_path:
            pass_metrics = self.test_pass_rate_from_junit_xml(junit_xml_path)
        elif test_total is not None and test_failures is not None:
            pass_metrics = self.test_pass_rate_from_counts(
                total=test_total,
                failures=test_failures,
                errors=test_errors,
            )
        else:
            pass_metrics = TestPassRate(passed=0, total=0, pass_rate=0.0)

        result["test_pass_rate"] = {
            "passed": pass_metrics.passed,
            "total": pass_metrics.total,
            "rate": pass_metrics.pass_rate,
        }
        return result
