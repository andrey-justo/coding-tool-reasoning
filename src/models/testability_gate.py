from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class VerificationCommandResult:
    status: str = "not-run"
    command: list[str] | None = None
    exit_code: int | None = None
    duration_seconds: float | None = None
    stdout_tail: str | None = None
    stderr_tail: str | None = None
    timed_out: bool | None = None


@dataclass
class VerificationCoverageResult:
    available: bool = False
    path: str | None = None


@dataclass
class VerificationJunitResult:
    available: bool = False
    path: str | None = None
    totals: dict[str, int] | None = None


@dataclass
class TestabilityGateStatus:
    build_status: str = "not-run"
    test_status: str = "not-run"
    reason: str = "Gate not executed."


@dataclass
class TestPassRateResult:
    rate: float
    total: int
    passed: int
    failures: int
    errors: int


@dataclass
class VerifyTestabilityGateResult:
    enabled: bool = True
    build: VerificationCommandResult = field(default_factory=VerificationCommandResult)
    test: VerificationCommandResult = field(default_factory=VerificationCommandResult)
    coverage: VerificationCoverageResult = field(default_factory=VerificationCoverageResult)
    junit: VerificationJunitResult = field(default_factory=VerificationJunitResult)
    testability_gate: TestabilityGateStatus = field(default_factory=TestabilityGateStatus)
    test_pass_rate_source: str = "not-run"
    test_pass_rate: TestPassRateResult | None = None
    log_lines: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
