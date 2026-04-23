"""Reproducibility experiment scaffold — implements the RQ2 methodology.

Measures output variance when the same software engineering intent is
submitted N times to the supervisor pipeline versus an unsupervised
(no taxonomy enrichment) baseline.

RQ2: Does the supervisor agent reduce output variance when the same
software engineering intent is submitted repeatedly to an LLM,
compared to an unsupervised baseline?

Usage (CLI):
    python -m src.evaluation.reproducibility_experiment \\
        --prompt "Refactor the authentication service to improve maintainability." \\
        --trials 10 \\
        --output reproducibility_results.json

The script prints a JSON report with per-trial verdicts, BERTScore F1 values,
and summary statistics (mean, std-dev, consistency ratio) for both the
supervised and baseline conditions.
"""

from __future__ import annotations

import argparse
import json
import statistics
from dataclasses import dataclass, field
from typing import List, Optional


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class TrialResult:
    """Result of a single supervisor or baseline trial."""

    trial_index: int
    verdict: str
    confidence: float
    bertscore_f1: Optional[float]
    plan_step_count: int
    nfr_coverage: float  # fraction of expected NFRs covered in nfr_impacts


@dataclass
class ReproducibilityReport:
    """Aggregated report for one prompt across N supervised and N baseline trials."""

    prompt: str
    n_trials: int
    reference_code: Optional[str]

    supervised: List[TrialResult] = field(default_factory=list)
    baseline: List[TrialResult] = field(default_factory=list)

    # ------------------------------------------------------------------ stats

    def _majority_verdict(self, trials: List[TrialResult]) -> str:
        if not trials:
            return "n/a"
        counts: dict[str, int] = {}
        for t in trials:
            counts[t.verdict] = counts.get(t.verdict, 0) + 1
        return max(counts, key=lambda k: counts[k])

    def _consistency_ratio(self, trials: List[TrialResult]) -> float:
        """Fraction of trials that agree with the majority verdict."""
        if not trials:
            return 0.0
        majority = self._majority_verdict(trials)
        return sum(1 for t in trials if t.verdict == majority) / len(trials)

    def _f1_stats(self, trials: List[TrialResult]) -> dict:
        f1_values = [t.bertscore_f1 for t in trials if t.bertscore_f1 is not None]
        if not f1_values:
            return {"mean": None, "stdev": None, "min": None, "max": None}
        return {
            "mean": statistics.mean(f1_values),
            "stdev": statistics.stdev(f1_values) if len(f1_values) > 1 else 0.0,
            "min": min(f1_values),
            "max": max(f1_values),
        }

    def _confidence_stats(self, trials: List[TrialResult]) -> dict:
        conf_values = [t.confidence for t in trials]
        if not conf_values:
            return {"mean": None, "stdev": None}
        return {
            "mean": statistics.mean(conf_values),
            "stdev": statistics.stdev(conf_values) if len(conf_values) > 1 else 0.0,
        }

    def summary(self) -> dict:
        """Return a JSON-serializable summary dict."""
        return {
            "prompt": self.prompt,
            "n_trials": self.n_trials,
            "supervised": {
                "majority_verdict": self._majority_verdict(self.supervised),
                "verdict_consistency_ratio": self._consistency_ratio(self.supervised),
                "bertscore_f1": self._f1_stats(self.supervised),
                "confidence": self._confidence_stats(self.supervised),
                "trials": [
                    {
                        "trial": t.trial_index,
                        "verdict": t.verdict,
                        "confidence": t.confidence,
                        "bertscore_f1": t.bertscore_f1,
                        "plan_step_count": t.plan_step_count,
                        "nfr_coverage": t.nfr_coverage,
                    }
                    for t in self.supervised
                ],
            },
            "baseline": {
                "majority_verdict": self._majority_verdict(self.baseline),
                "verdict_consistency_ratio": self._consistency_ratio(self.baseline),
                "bertscore_f1": self._f1_stats(self.baseline),
                "confidence": self._confidence_stats(self.baseline),
                "trials": [
                    {
                        "trial": t.trial_index,
                        "verdict": t.verdict,
                        "confidence": t.confidence,
                        "bertscore_f1": t.bertscore_f1,
                        "plan_step_count": t.plan_step_count,
                        "nfr_coverage": t.nfr_coverage,
                    }
                    for t in self.baseline
                ],
            },
        }


# ---------------------------------------------------------------------------
# Experiment runner
# ---------------------------------------------------------------------------


class ReproducibilityExperiment:
    """Runs the RQ2 reproducibility experiment for a single prompt.

    For each trial:
    1. Supervised path: plan_swe_code_change → build_swe_code_context →
       (external LLM generates code) → judge_swe_code_change.
    2. Baseline path: raw LLM call with the same prompt but without taxonomy
       enrichment (no IntentPlanner, no ExplanationService taxonomy context).

    The two paths are run for n_trials iterations each.  Both use
    temperature=0 and a fixed seed to ensure that variance comes from
    the LLM's stochastic process, not from prompt differences across runs.
    """

    def __init__(
        self,
        n_trials: int = 10,
        reference_code: Optional[str] = None,
    ) -> None:
        self.n_trials = n_trials
        self.reference_code = reference_code

    def run(self, prompt: str) -> ReproducibilityReport:
        """Execute all trials and return a filled ReproducibilityReport.

        NOTE: This method is a scaffold. Wire in the real MCP tool calls and
        LLM client calls when implementing the empirical study.
        """
        report = ReproducibilityReport(
            prompt=prompt,
            n_trials=self.n_trials,
            reference_code=self.reference_code,
        )

        for i in range(self.n_trials):
            # --- supervised trial ----------------------------------------
            supervised_result = self._run_supervised_trial(i, prompt)
            report.supervised.append(supervised_result)

            # --- baseline trial ------------------------------------------
            baseline_result = self._run_baseline_trial(i, prompt)
            report.baseline.append(baseline_result)

        return report

    def _run_supervised_trial(self, index: int, prompt: str) -> TrialResult:
        """Supervised path: IntentPlanner → ExplanationService.

        TODO: Replace placeholders with real MCP tool invocations:
          1. plan  = IntentPlanner(...).plan(prompt)
          2. ctx   = build_swe_code_context(plan, ...)
          3. code  = llm_client.chat(ctx.swe_summary + prompt, temperature=0, seed=42)
          4. expl  = ExplanationService(...).explain_change(ctx, original_code, code)
          5. Return TrialResult populated from expl and BERTScore evaluation.
        """
        raise NotImplementedError(
            "Supervised trial not yet wired. See TODO in _run_supervised_trial."
        )

    def _run_baseline_trial(self, index: int, prompt: str) -> TrialResult:
        """Baseline path: raw LLM call, no taxonomy enrichment.

        TODO: Replace placeholder with a direct llm_client.chat call at
          temperature=0 and seed=42, then evaluate via ReliabilityEvaluationTool.
        """
        raise NotImplementedError(
            "Baseline trial not yet wired. See TODO in _run_baseline_trial."
        )


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="RQ2 reproducibility experiment for the SWE-NFR supervisor agent."
    )
    parser.add_argument(
        "--prompt", required=True, help="Natural language SE intent to test."
    )
    parser.add_argument(
        "--trials",
        type=int,
        default=10,
        help="Number of repeated trials per condition (default: 10; paper recommends 30).",
    )
    parser.add_argument(
        "--reference",
        default=None,
        help="Path to a reference implementation file for BERTScore evaluation.",
    )
    parser.add_argument(
        "--output",
        default="reproducibility_results.json",
        help="Path to write the JSON report.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    reference_code: Optional[str] = None
    if args.reference:
        with open(args.reference, "r", encoding="utf-8") as f:
            reference_code = f.read()

    experiment = ReproducibilityExperiment(
        n_trials=args.trials,
        reference_code=reference_code,
    )
    report = experiment.run(prompt=args.prompt)
    summary = report.summary()

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"Report written to {args.output}")
    print(
        f"Supervised verdict consistency: "
        f"{summary['supervised']['verdict_consistency_ratio']:.2%}"
    )
    print(
        f"Baseline   verdict consistency: "
        f"{summary['baseline']['verdict_consistency_ratio']:.2%}"
    )


if __name__ == "__main__":
    main()
