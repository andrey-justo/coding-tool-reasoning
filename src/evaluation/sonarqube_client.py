from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import requests


@dataclass(frozen=True)
class SonarIssueQuery:
    project_key: str
    branch: str | None = None
    pull_request: str | None = None
    rule_keys: Sequence[str] | None = None
    severities: Sequence[str] | None = None
    component_keys: Sequence[str] | None = None


class SonarQubeClient:
    """Minimal SonarQube API client for issue counting."""

    def __init__(self, base_url: str, token: str, timeout: int = 30) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._session = requests.Session()
        # SonarQube token auth: token as username, blank password.
        self._session.auth = (token, "")

    def count_issues(self, query: SonarIssueQuery) -> int:
        params: dict[str, str] = {
            "projects": query.project_key,
            "resolved": "false",
            "ps": "500",
            "p": "1",
        }

        if query.branch:
            params["branch"] = query.branch
        if query.pull_request:
            params["pullRequest"] = query.pull_request
        if query.rule_keys:
            params["rules"] = ",".join(
                [value.strip() for value in query.rule_keys if value.strip()]
            )
        if query.severities:
            params["severities"] = ",".join(
                [value.strip().upper() for value in query.severities if value.strip()]
            )
        if query.component_keys:
            params["componentKeys"] = ",".join(
                [value.strip() for value in query.component_keys if value.strip()]
            )

        total = 0
        page = 1

        while True:
            params["p"] = str(page)
            response = self._session.get(
                f"{self._base_url}/api/issues/search",
                params=params,
                timeout=self._timeout,
            )
            response.raise_for_status()
            payload = response.json()

            paging = payload.get("paging") or {}
            issues = payload.get("issues") or []
            total += len(issues)

            page_size = int(paging.get("pageSize") or 500)
            total_items = int(paging.get("total") or 0)
            if page * page_size >= total_items:
                break
            page += 1

        return total
