from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ParsedIssueUrl:
    owner: str
    repo: str
    issue_number: int
    url: str
