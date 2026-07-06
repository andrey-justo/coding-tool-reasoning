from __future__ import annotations

import requests

from src.evaluation.sonarqube_client import SonarIssueQuery, SonarQubeClient


class _FakeResponse:
    def __init__(self, payload: dict, should_raise: bool = False):
        self._payload = payload
        self._should_raise = should_raise

    def raise_for_status(self) -> None:
        if self._should_raise:
            raise requests.HTTPError("boom")

    def json(self) -> dict:
        return self._payload


class _FakeSession:
    def __init__(self, responses: list[_FakeResponse]):
        self._responses = responses
        self.auth = None
        self.calls: list[dict] = []

    def get(self, url: str, params: dict, timeout: int):
        self.calls.append({"url": url, "params": dict(params), "timeout": timeout})
        return self._responses[len(self.calls) - 1]


def test_count_issues_builds_params_and_counts_single_page() -> None:
    client = SonarQubeClient(base_url="https://sonar.example/", token="token", timeout=7)
    client._session = _FakeSession(
        [_FakeResponse({"paging": {"pageSize": 500, "total": 2}, "issues": [{}, {}]})]
    )

    query = SonarIssueQuery(
        project_key="proj",
        branch="main",
        pull_request="12",
        rule_keys=[" rule1 ", "", "rule2"],
        severities=[" blocker ", "major"],
        component_keys=[" src/a.py ", "src/b.py"],
    )

    total = client.count_issues(query)

    assert total == 2
    call = client._session.calls[0]
    assert call["url"].endswith("/api/issues/search")
    assert call["timeout"] == 7
    assert call["params"]["projects"] == "proj"
    assert call["params"]["branch"] == "main"
    assert call["params"]["pullRequest"] == "12"
    assert call["params"]["rules"] == "rule1,rule2"
    assert call["params"]["severities"] == "BLOCKER,MAJOR"
    assert call["params"]["componentKeys"] == "src/a.py,src/b.py"


def test_count_issues_handles_pagination() -> None:
    client = SonarQubeClient(base_url="https://sonar.example", token="token")
    client._session = _FakeSession(
        [
            _FakeResponse({"paging": {"pageSize": 2, "total": 3}, "issues": [{}, {}]}),
            _FakeResponse({"paging": {"pageSize": 2, "total": 3}, "issues": [{}]}),
        ]
    )

    total = client.count_issues(SonarIssueQuery(project_key="proj"))

    assert total == 3
    assert len(client._session.calls) == 2
    assert client._session.calls[0]["params"]["p"] == "1"
    assert client._session.calls[1]["params"]["p"] == "2"


def test_count_issues_propagates_http_error() -> None:
    client = SonarQubeClient(base_url="https://sonar.example", token="token")
    client._session = _FakeSession([_FakeResponse({}, should_raise=True)])

    try:
        client.count_issues(SonarIssueQuery(project_key="proj"))
        raise AssertionError("Expected HTTPError")
    except requests.HTTPError:
        pass
