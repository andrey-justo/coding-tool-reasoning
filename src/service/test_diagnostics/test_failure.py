from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class TestFailure:
    """One failing test normalized across test runners."""

    __test__ = False

    test_name: str
    message: str = ""
    class_name: str | None = None
    stack_trace: str = ""
    file: str | None = None
    line: int | None = None
    outcome: str = "failed"
    raw: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TestFailuresResult:
    """Failing tests extracted from one test run by one parser."""

    __test__ = False

    parser: str
    available: bool = True
    failures: list[TestFailure] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "parser": self.parser,
            "available": self.available,
            "failures": [failure.to_dict() for failure in self.failures],
        }
