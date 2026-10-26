from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

from src.experiments.issue_mcp_experiment import (
    _repair_tests_until_pass,
    _sanitize_test_repair_rounds,
)


class _FakeSession:
    """MCP session stub returning scripted repair_test_failure payloads."""

    def __init__(self, payloads: list[dict]) -> None:
        self._payloads = payloads
        self.calls: list[dict] = []

    async def call_tool(self, name: str, arguments: dict):
        self.calls.append({"name": name, "arguments": arguments})
        payload = self._payloads[min(len(self.calls) - 1, len(self._payloads) - 1)]
        return SimpleNamespace(content=[SimpleNamespace(text=json.dumps(payload))])


def _gate(
    test_status: str, *, build_status: str = "pass", pass_rate: float | None = 0.97
) -> dict:
    return {
        "build": {"status": build_status, "command": ["dotnet", "build"]},
        "test": {
            "status": test_status,
            "command": ["dotnet", "test"],
            "stdout_tail": "Failed Spec.Should_not_report_AKKASG011_for_arrays",
            "stderr_tail": "",
        },
        "junit": {"available": True, "path": "C:/gate/results.trx"},
        "test_pass_rate": pass_rate,
    }


def _repair_payload(*, changed: bool, code: str = "fixed") -> dict:
    return {
        "attempt": 1,
        "max_attempts": 10,
        "failures_parser": "trx",
        "failures_by_file": {"a.cs": [{"test_name": "spec", "line": 3}]},
        "unmatched_failures": [],
        "repair_targets": ["a.cs"],
        "repaired_files": ["a.cs"] if changed else [],
        "changed": changed,
        "generated_code_by_file": {"a.cs": code} if changed else {"a.cs": "broken"},
        "file_results": [
            {
                "target_file": "a.cs",
                "prompt": "p" * 10,
                "raw_response": "r" * 4,
                "changed": changed,
                "failure_count": 1,
                "matched_by_stack_trace": True,
                "related_files": [],
                "ast_context_available": True,
            }
        ],
    }


def _run_loop(session, gates: list[dict], *, max_attempts: int = 10, recover=None):
    generated = {"a.cs": "broken"}
    apply_results: dict[str, dict] = {"a.cs": {"generated_code": "broken"}}
    remaining = list(gates)

    async def run_gate(_code_by_file):
        return remaining.pop(0)

    log_lines: list[str] = []
    gate, rounds = asyncio.run(
        _repair_tests_until_pass(
            session=session,
            verification_gate=_gate("fail"),
            generated_code_by_file=generated,
            apply_results=apply_results,
            problem_summary="summary",
            temperature=0.0,
            seed=7,
            max_attempts=max_attempts,
            run_gate=run_gate,
            log_lines=log_lines,
            recover_build=recover,
        )
    )
    return gate, rounds, generated, apply_results, log_lines


def test_loop_stops_once_tests_pass() -> None:
    session = _FakeSession([_repair_payload(changed=True)])

    gate, rounds, generated, apply_results, _ = _run_loop(
        session, [_gate("pass", pass_rate=1.0)]
    )

    assert gate["test"]["status"] == "pass"
    assert len(rounds) == 1
    assert rounds[0]["test_status_before"] == "fail"
    assert rounds[0]["test_status_after"] == "pass"
    assert rounds[0]["test_pass_rate_before"] == 0.97
    assert rounds[0]["test_pass_rate_after"] == 1.0
    assert generated["a.cs"] == "fixed"
    assert apply_results["a.cs"]["test_repair_applied"] is True
    assert session.calls[0]["name"] == "repair_test_failure"
    assert session.calls[0]["arguments"]["results_path"] == "C:/gate/results.trx"


def test_loop_respects_attempt_budget_when_it_never_converges() -> None:
    session = _FakeSession([_repair_payload(changed=True)])

    _, rounds, _, _, _ = _run_loop(
        session, [_gate("fail") for _ in range(3)], max_attempts=3
    )

    assert len(rounds) == 3
    assert len(session.calls) == 3


def test_loop_stops_when_repair_changes_nothing() -> None:
    session = _FakeSession([_repair_payload(changed=False)])

    _, rounds, generated, _, _ = _run_loop(session, [])

    assert len(rounds) == 1
    assert rounds[0]["stopped_reason"]
    assert generated["a.cs"] == "broken"
    assert len(session.calls) == 1


def test_loop_is_disabled_when_budget_is_zero() -> None:
    session = _FakeSession([_repair_payload(changed=True)])

    _, rounds, _, _, _ = _run_loop(session, [], max_attempts=0)

    assert rounds == []
    assert session.calls == []


def test_loop_recovers_the_build_when_a_test_repair_breaks_compilation() -> None:
    session = _FakeSession([_repair_payload(changed=True)])
    recovery_calls: list[dict] = []

    async def recover(gate: dict):
        recovery_calls.append(gate)
        return _gate("pass", build_status="pass", pass_rate=1.0), [{"attempt": 1}]

    gate, rounds, _, _, _ = _run_loop(
        session,
        [_gate("fail", build_status="fail")],
        recover=recover,
    )

    assert len(recovery_calls) == 1
    assert rounds[0]["build_recovery_rounds"] == 1
    assert rounds[0]["build_status_after"] == "pass"
    assert rounds[0]["test_status_after"] == "pass"
    assert gate["build"]["status"] == "pass"


def test_sanitize_replaces_prompts_with_sizes() -> None:
    rounds = [
        {
            **_repair_payload(changed=True),
            "test_status_before": "fail",
            "test_status_after": "pass",
            "build_status_after": "pass",
        }
    ]

    sanitized = _sanitize_test_repair_rounds(rounds)

    assert len(sanitized) == 1
    file_result = sanitized[0]["file_results"][0]
    assert "prompt" not in file_result
    assert "raw_response" not in file_result
    assert file_result["prompt_chars"] == 10
    assert file_result["raw_response_chars"] == 4
    assert sanitized[0]["test_status_after"] == "pass"
    assert sanitized[0]["repair_targets"] == ["a.cs"]


def test_sanitize_handles_missing_or_invalid_payloads() -> None:
    assert _sanitize_test_repair_rounds(None) == []
    assert _sanitize_test_repair_rounds(["not-a-dict"]) == []
