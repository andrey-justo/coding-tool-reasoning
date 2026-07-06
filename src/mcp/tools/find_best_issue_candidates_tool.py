from __future__ import annotations

from src.models.issue_candidate_ranking import (
    IssueCandidate,
    IssueCandidateRankingResult,
    PullRequestContext,
)
from src.service.issue_candidate_ranking_service import IssueCandidateRankingService


class FindBestIssueCandidatesTool:
    """Class-based issue ranking tool for easier mocking and unit testing."""

    def __init__(self, registry) -> None:
        self._registry = registry

    def execute(
        self,
        current_pr: PullRequestContext,
        issue_candidates: list[IssueCandidate],
        top_k: int = 5,
        min_score: float = 0.15,
        target_language: str | None = None,
        nfr_focus: list[str] | None = None,
    ) -> IssueCandidateRankingResult:
        """Rank issue candidates based on current PR context for agent follow-up."""

        service_cls = (
            self._registry._issue_candidate_ranking_service_cls
            or IssueCandidateRankingService
        )
        service = service_cls(plan_builder=self._registry.plan_swe_code_change)

        return service.rank_candidates(
            current_pr=current_pr,
            issue_candidates=issue_candidates,
            top_k=top_k,
            min_score=min_score,
            target_language=target_language,
            nfr_focus=nfr_focus,
        )
