from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class LLMEvaluation:
    score: Optional[float]
    rationale: str


class ReadabilityMetricsStrategy:
    """Readability metrics including heuristic proxy and optional LLM rating."""

    def buse_weimer_readability_proxy(self, code: str) -> float:
        lines = code.splitlines()
        if not lines:
            return 0.0

        non_empty = [line for line in lines if line.strip()]
        if not non_empty:
            return 0.0

        avg_line_len = sum(len(line) for line in non_empty) / len(non_empty)
        long_line_penalty = min(avg_line_len / 120.0, 1.0)

        comment_lines = sum(
            1
            for line in lines
            if line.strip().startswith("#") or line.strip().startswith("//")
        )
        comment_ratio = comment_lines / len(non_empty)

        blank_ratio = (len(lines) - len(non_empty)) / max(len(lines), 1)

        max_indent = 0
        for line in non_empty:
            stripped = line.lstrip(" ")
            indent = len(line) - len(stripped)
            max_indent = max(max_indent, indent)
        indent_penalty = min(max_indent / 16.0, 1.0)

        raw = (
            0.40 * (1.0 - long_line_penalty)
            + 0.20 * min(comment_ratio / 0.2, 1.0)
            + 0.20 * (1.0 - indent_penalty)
            + 0.20 * min(blank_ratio / 0.25, 1.0)
        )
        return max(0.0, min(raw, 1.0))

    def llm_readability_evaluation(
        self,
        code: str,
        llm_client: Any,
        model: Optional[str] = None,
    ) -> LLMEvaluation:
        prompt = (
            "You are evaluating source code readability. "
            "Return strict JSON with keys: score (0 to 1), rationale (short text).\n"
            "Focus on naming clarity, structure, and maintainability.\n\n"
            f"Code:\n```\n{code}\n```"
        )
        try:
            response = llm_client.chat(prompt, model=model) if model else llm_client.chat(prompt)
            payload = json.loads(response)
            score = payload.get("score")
            if score is not None:
                score = float(score)
                score = max(0.0, min(score, 1.0))
            rationale = str(payload.get("rationale", ""))
            return LLMEvaluation(score=score, rationale=rationale)
        except Exception as exc:
            return LLMEvaluation(score=None, rationale=f"LLM evaluation unavailable: {exc}")

    def compute(
        self,
        code: str,
        llm_client: Any | None = None,
        llm_model: str | None = None,
    ) -> dict[str, Any]:
        result: dict[str, Any] = {
            "buse_weimer_proxy": self.buse_weimer_readability_proxy(code),
        }

        if llm_client is not None:
            llm_eval = self.llm_readability_evaluation(
                code=code,
                llm_client=llm_client,
                model=llm_model,
            )
            result["llm_evaluation"] = {
                "score": llm_eval.score,
                "rationale": llm_eval.rationale,
            }
        else:
            result["llm_evaluation"] = None

        return result
