from types import SimpleNamespace

from src.models.issue_candidate_ranking import IssueCandidate, PullRequestContext
from src.service.issue_candidate_ranking_service import IssueCandidateRankingService


def test_issue_candidate_ranking_service_orders_more_relevant_issue_first():
    captured = {"problem_description": "", "user_prompt_data": ""}

    def fake_plan_builder(
        problem_description, target_language=None, nfr_focus=None, user_prompt_data=None
    ):
        captured["problem_description"] = problem_description
        captured["user_prompt_data"] = user_prompt_data
        return SimpleNamespace(
            nfr_focus=nfr_focus or ["Reliability", "Maintainability"],
        )

    service = IssueCandidateRankingService(plan_builder=fake_plan_builder)
    result = service.rank_candidates(
        current_pr=PullRequestContext(
            title="Improve reliability of auth retry flow",
            description="Refactor retry backoff and reduce duplicated logic.",
            changed_files=["src/service/auth_service.py"],
        ),
        issue_candidates=[
            IssueCandidate(
                issue_id="401",
                title="Auth retry flow fails under transient errors",
                body="Reliability issue in auth service retries.",
                labels=["reliability"],
                related_files=["src/service/auth_service.py"],
            ),
            IssueCandidate(
                issue_id="402",
                title="Tune homepage spacing",
                body="Visual polish only.",
                labels=["frontend"],
                related_files=["src/ui/home.css"],
            ),
        ],
        top_k=2,
        min_score=0.0,
    )

    assert "PR title: Improve reliability of auth retry flow" in captured[
        "problem_description"
    ]
    assert captured["user_prompt_data"] == "Issue candidate ranking context"

    assert result.total_candidates == 2
    assert result.returned_candidates == 2
    assert result.ranked_candidates[0].issue_id == "401"
    assert result.ranked_candidates[0].score > result.ranked_candidates[1].score


def test_issue_candidate_ranking_service_applies_threshold_and_top_k():
    def fake_plan_builder(
        problem_description, target_language=None, nfr_focus=None, user_prompt_data=None
    ):
        return SimpleNamespace(nfr_focus=["Reliability"])

    service = IssueCandidateRankingService(plan_builder=fake_plan_builder)
    result = service.rank_candidates(
        current_pr=PullRequestContext(
            title="Reliability fix for auth retries",
            description="",
            changed_files=["src/service/auth_service.py"],
        ),
        issue_candidates=[
            IssueCandidate(
                issue_id="501",
                title="Reliability bug in auth retries",
                body="",
                labels=["reliability"],
                related_files=["src/service/auth_service.py"],
            ),
            IssueCandidate(
                issue_id="502",
                title="Docs cleanup",
                body="Readme grammar update.",
                labels=["documentation"],
                related_files=["README.md"],
            ),
        ],
        top_k=1,
        min_score=0.3,
    )

    assert result.total_candidates == 2
    assert result.returned_candidates == 1
    assert len(result.ranked_candidates) == 1
    assert result.ranked_candidates[0].issue_id == "501"
