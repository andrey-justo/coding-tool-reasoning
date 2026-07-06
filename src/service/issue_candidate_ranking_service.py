from __future__ import annotations

import os
import re
from typing import Callable, List, Optional

from src.models.code_gen_plan import CodeGenPlan
from src.models.issue_candidate_ranking import (
    IssueCandidate,
    IssueCandidateRankingResult,
    PullRequestContext,
    RankedIssueCandidate,
)


class IssueCandidateRankingService:
    """Ranks GitHub issue candidates against the current PR context."""

    def __init__(self, plan_builder: Callable[..., CodeGenPlan]) -> None:
        self._plan_builder = plan_builder

    def rank_candidates(
        self,
        current_pr: PullRequestContext,
        issue_candidates: List[IssueCandidate],
        top_k: int = 5,
        min_score: float = 0.15,
        target_language: Optional[str] = None,
        nfr_focus: Optional[List[str]] = None,
    ) -> IssueCandidateRankingResult:
        """Return top ranked issue candidates for the given PR."""

        description = current_pr.description or ""
        changed_files_text = "\n".join(current_pr.changed_files)
        pr_problem_description = (
            f"PR title: {current_pr.title}\n"
            f"PR description:\n{description}\n"
            f"Changed files:\n{changed_files_text}"
        )

        plan = self._plan_builder(
            problem_description=pr_problem_description,
            target_language=target_language,
            nfr_focus=nfr_focus,
            user_prompt_data="Issue candidate ranking context",
        )

        pr_text = self._normalize_text(pr_problem_description)
        pr_tokens = self._tokenize(pr_text)
        pr_nfr_map = {n.lower(): n for n in plan.nfr_focus}
        pr_file_names = {
            os.path.basename(path).lower() for path in current_pr.changed_files if path
        }

        ranked: List[RankedIssueCandidate] = []
        bounded_top_k = max(1, top_k)
        bounded_min_score = max(0.0, min(1.0, min_score))

        for issue in issue_candidates:
            issue_text = self._normalize_text(
                "\n".join(
                    [
                        issue.title,
                        issue.body or "",
                        " ".join(issue.labels),
                        " ".join(issue.related_files),
                    ]
                )
            )
            issue_tokens = self._tokenize(issue_text)

            lexical_score = self._jaccard_similarity(pr_tokens, issue_tokens)

            matched_nfrs = [
                original
                for lowered, original in pr_nfr_map.items()
                if lowered in issue_text
            ]
            nfr_score = (
                len(matched_nfrs) / len(pr_nfr_map) if pr_nfr_map else 0.0
            )

            issue_file_names = {
                os.path.basename(path).lower() for path in issue.related_files if path
            }
            matched_files = sorted(pr_file_names.intersection(issue_file_names))
            file_score = (
                len(matched_files) / len(pr_file_names) if pr_file_names else 0.0
            )

            score = (0.55 * lexical_score) + (0.30 * nfr_score) + (0.15 * file_score)
            score = max(0.0, min(1.0, round(score, 4)))

            if score < bounded_min_score:
                continue

            reasons = [
                f"Lexical alignment score: {lexical_score:.2f}",
                f"NFR overlap score: {nfr_score:.2f}",
                f"File overlap score: {file_score:.2f}",
            ]

            ranked.append(
                RankedIssueCandidate(
                    issue_id=issue.issue_id,
                    title=issue.title,
                    score=score,
                    matched_nfrs=sorted(matched_nfrs),
                    matched_files=matched_files,
                    reasons=reasons,
                )
            )

        ranked.sort(key=lambda candidate: (-candidate.score, candidate.issue_id))
        ranked = ranked[:bounded_top_k]

        return IssueCandidateRankingResult(
            inferred_nfr_focus=plan.nfr_focus,
            total_candidates=len(issue_candidates),
            returned_candidates=len(ranked),
            ranked_candidates=ranked,
        )

    @staticmethod
    def _normalize_text(value: str) -> str:
        return value.lower().strip()

    @staticmethod
    def _tokenize(value: str) -> set[str]:
        return {
            token
            for token in re.findall(r"[a-z0-9_\-/]+", value)
            if len(token) > 2
        }

    @staticmethod
    def _jaccard_similarity(left: set[str], right: set[str]) -> float:
        if not left or not right:
            return 0.0
        intersection = len(left.intersection(right))
        union = len(left.union(right))
        if union == 0:
            return 0.0
        return intersection / union