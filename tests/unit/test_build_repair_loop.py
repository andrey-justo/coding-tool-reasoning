from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

from src.experiments.issue_mcp_experiment import (
    _repair_build_until_pass,
    _sanitize_build_repair_rounds,
)


class _FakeSession:
    """MCP session stub returning scripted repair_build_failure payloads."""

    def __init__(self, payloads: list[dict]) -> None:
        self._payloads = payloads
        self.calls: list[dict] = []

    async def call_tool(self, name: str, arguments: dict):
        self.calls.append({"name": name, "arguments": arguments})
        payload = self._payloads[min(len(self.calls) - 1, len(self._payloads) - 1)]
        return SimpleNamespace(
            content=[SimpleNamespace(text=json.dumps(payload))],
        )


def _gate(status: str) -> dict:
    return {
        "build": {
            "status": status,
            "command": ["dotnet", "build"],
            "stdout_tail": "a.cs(1,1): error CS1503: bad [a.csproj]",
            "stderr_tail": "",
        }
    }


def _repair_payload(*, changed: bool, code: str = "fixed") -> dict:
    return {
        "attempt": 1,
        "max_attempts": 10,
        "diagnostics_parser": "dotnet",
        "diagnostics_by_file": {"a.cs": [{"code": "CS1503"}]},
        "unmatched_diagnostics": [],
        "repaired_files": ["a.cs"] if changed else [],
        "changed": changed,
        "generated_code_by_file": {"a.cs": code} if changed else {"a.cs": "broken"},
        "file_results": [
            {
                "target_file": "a.cs",
                "prompt": "p" * 10,
                "raw_response": "r" * 4,
                "changed": changed,
                "diagnostic_count": 1,
                "ast_context_available": True,
            }
        ],
    }


def _run_loop(session, gates: list[dict], *, max_attempts: int = 10):
    generated = {"a.cs": "broken"}
    apply_results: dict[str, dict] = {"a.cs": {"generated_code": "broken"}}
    remaining = list(gates)

    async def run_gate(_code_by_file):
        return remaining.pop(0)

    log_lines: list[str] = []
    gate, rounds = asyncio.run(
        _repair_build_until_pass(
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
        )
    )
    return gate, rounds, generated, apply_results, log_lines


def test_loop_stops_once_build_passes() -> None:
    session = _FakeSession([_repair_payload(changed=True)])

    gate, rounds, generated, apply_results, _ = _run_loop(session, [_gate("pass")])

    assert gate["build"]["status"] == "pass"
    assert len(rounds) == 1
    assert rounds[0]["build_status_before"] == "fail"
    assert rounds[0]["build_status_after"] == "pass"
    assert generated["a.cs"] == "fixed"
    assert apply_results["a.cs"]["build_repair_applied"] is True
    assert len(session.calls) == 1
    assert session.calls[0]["name"] == "repair_build_failure"


def test_loop_respects_attempt_budget_when_it_never_converges() -> None:
    session = _FakeSession([_repair_payload(changed=True)])

    _, rounds, _, _, _ = _run_loop(
        session, [_gate("fail") for _ in range(3)], max_attempts=3
    )

    assert len(rounds) == 3
    assert len(session.calls) == 3
    assert all(round_["build_status_after"] == "fail" for round_ in rounds)


def test_loop_escalates_routing_once_before_giving_up() -> None:
    """A target that cannot be repaired is not where the fix belongs."""

    session = _FakeSession([_repair_payload(changed=False)])

    _, rounds, generated, _, _ = _run_loop(session, [])

    assert len(rounds) == 2
    assert len(session.calls) == 2
    assert session.calls[0]["arguments"]["escalate_routing"] is False
    assert session.calls[1]["arguments"]["escalate_routing"] is True
    assert "escalating routing" in rounds[0]["stopped_reason"]
    assert "escalating routing" not in rounds[1]["stopped_reason"]
    assert generated["a.cs"] == "broken"


def test_loop_does_not_escalate_when_no_budget_remains() -> None:
    session = _FakeSession([_repair_payload(changed=False)])

    _, rounds, _, _, _ = _run_loop(session, [], max_attempts=1)

    assert len(rounds) == 1
    assert len(session.calls) == 1
    assert "escalating routing" not in rounds[0]["stopped_reason"]


def test_loop_is_disabled_when_budget_is_zero() -> None:
    session = _FakeSession([_repair_payload(changed=True)])

    _, rounds, _, _, _ = _run_loop(session, [], max_attempts=0)

    assert rounds == []
    assert session.calls == []


def test_sanitize_replaces_prompts_with_sizes() -> None:
    rounds = [
        {
            **_repair_payload(changed=True),
            "build_status_before": "fail",
            "build_status_after": "pass",
        }
    ]

    sanitized = _sanitize_build_repair_rounds(rounds)

    assert len(sanitized) == 1
    file_result = sanitized[0]["file_results"][0]
    assert "prompt" not in file_result
    assert "raw_response" not in file_result
    assert file_result["prompt_chars"] == 10
    assert file_result["raw_response_chars"] == 4
    assert sanitized[0]["build_status_after"] == "pass"


def test_sanitize_handles_missing_or_invalid_payloads() -> None:
    assert _sanitize_build_repair_rounds(None) == []
    assert _sanitize_build_repair_rounds(["not-a-dict"]) == []
