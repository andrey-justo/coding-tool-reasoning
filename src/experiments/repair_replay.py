"""Replay saved sources using LLM-controlled repair and factual verification."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from mcp.types import CallToolResult, TextContent

from src.experiments.issue_mcp_experiment import _base_ref_worktree
from src.experiments.repair_agent_loop import (
    _full_verification_passed,
    canonical_source_path,
    repair_with_agent,
)
from src.mcp.swe_mcp_server import SweMcpServerContextProvider
from src.mcp.tools.swe_mcp_tools import SweMcpToolRegistry
from src.service.source_identity import sources_fingerprint


def load_frozen_candidate(report: dict[str, Any]) -> dict[str, str]:
    sources: dict[str, str] = {}
    for path in report["subject"]["target_files"]:
        canonical = canonical_source_path(path)
        if canonical in sources:
            raise ValueError("Saved source paths are duplicated.")
        result = report["mcp"]["apply_results"][path]
        source = result.get("generated_code")
        if result.get("error") or not isinstance(source, str) or not source.strip():
            raise ValueError(f"No usable saved source for {path}")
        sources[canonical] = source
    return sources


def run_repair_replay(
    *,
    report_path: Path,
    output_path: Path,
    max_attempts: int = 3,
    timeout_seconds: int = 300,
    max_seconds: float = 300,
    model: str | None = None,
    run_tests: bool = True,
    candidate_report: Path | None = None,
    candidate_attempt: int | None = None,
    mode: str = "loop",
    concurrency: int = 3,
) -> dict[str, Any]:
    if report_path.resolve() == output_path.resolve():
        raise ValueError("Replay output must not overwrite its source report.")
    if not 0 <= max_attempts <= 25 or timeout_seconds <= 0 or max_seconds <= 0:
        raise ValueError("Replay resource budgets are invalid.")
    raw = report_path.read_bytes()
    report = json.loads(raw)
    sources = load_frozen_candidate(report)
    initial_generated_sources = dict(sources)
    source_digest = hashlib.sha256(raw).hexdigest()
    provenance: dict[str, Any] = {
        "source_report": str(report_path.resolve()),
        "source_report_sha256": source_digest,
        "compile_only": not run_tests,
        "verification_scope": "full",
        "repair_mode": mode,
    }
    if candidate_report is not None:
        if candidate_report.resolve() == output_path.resolve():
            raise ValueError("Replay output must not overwrite its candidate report.")
        candidate_raw = candidate_report.read_bytes()
        saved = json.loads(candidate_raw)
        if saved.get("source_report_sha256") != source_digest:
            raise ValueError("Candidate report does not belong to this source report.")
        selected = saved
        if candidate_attempt is not None:
            selected = next(
                (
                    row
                    for row in saved.get("attempts", [])
                    if row.get("attempt") == candidate_attempt
                ),
                None,
            )
            if selected is None or not selected.get("changed"):
                raise ValueError("Selected candidate attempt has no changed sources.")
        candidate = selected.get("generated_code_by_file")
        if not isinstance(candidate, dict) or not sources.keys() <= candidate.keys():
            raise ValueError(
                "Saved candidate must contain the complete input file set."
            )
        normalized = {}
        for path, code in candidate.items():
            if not isinstance(code, str) or not code.strip():
                raise ValueError("Saved candidate contains invalid source.")
            canonical = canonical_source_path(path)
            if canonical in normalized:
                raise ValueError("Saved candidate has duplicate source paths.")
            normalized[canonical] = code
        if candidate_attempt is not None and selected.get(
            "candidate_sha256"
        ) != sources_fingerprint(normalized):
            raise ValueError("Saved candidate source fingerprint does not match.")
        sources = normalized
        provenance.update(
            candidate_report=str(candidate_report.resolve()),
            candidate_report_sha256=hashlib.sha256(candidate_raw).hexdigest(),
            candidate_attempt=candidate_attempt,
        )
    elif candidate_attempt is not None:
        raise ValueError("A candidate attempt requires its candidate report.")
    selected_model = model or report.get("run_config", {}).get("llm", {}).get("model")
    previous_model = os.environ.get("DEFAULT_MODEL")
    if selected_model:
        os.environ["DEFAULT_MODEL"] = selected_model
    provenance["model"] = selected_model
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        registry = SweMcpToolRegistry(
            SweMcpServerContextProvider().create_swe_server_context
        )
        subject = report["subject"]
        plan = report["mcp"]["plan"]
        problem = json.dumps(
            {
                "planning_and_requirements": plan,
                "knowledge_base_context": report["mcp"]
                .get("context", {})
                .get("swe_summary"),
            }
        )

        class ReplaySession:
            async def call_tool(
                self, name: str, arguments: dict[str, Any]
            ) -> CallToolResult:
                tools = {
                    "decide_repair_action": registry.decide_repair_action,
                    "review_repair_changes": registry.review_repair_changes,
                }
                if name not in tools:
                    raise ValueError(f"Unknown replay tool: {name}")
                response = await asyncio.to_thread(tools[name], **arguments)
                return CallToolResult(
                    content=[TextContent(type="text", text=json.dumps(response))]
                )

        def verify(candidate: dict[str, str]) -> dict[str, Any]:
            return registry.verify_testability_gate(
                repo_path=subject["repo_path"],
                base_ref=subject["base_ref"],
                generated_code_by_file=candidate,
                timeout_seconds=timeout_seconds,
                compile_only=not run_tests,
            )

        baseline = verify(dict(sources))
        baseline_totals = (baseline.get("junit") or {}).get("totals") or {}
        retained = dict(sources)
        result: dict[str, Any] = {
            **provenance,
            "accepted": False,
            "baseline_verification": baseline,
            "verification": baseline,
            "generated_code_by_file": retained,
            "attempts": [],
            "stopped_reason": (
                "Verification-only replay; no model repair requested."
                if max_attempts == 0
                else "Repair not completed; input retained."
            ),
        }

        def persist(gate, current, rounds):
            result.update(
                accepted=current != sources,
                verification=gate,
                generated_code_by_file=current,
                attempts=rounds,
                full_build_and_tests_passed=(
                    run_tests
                    and _full_verification_passed(
                        gate,
                        True,
                        int(baseline_totals.get("tests") or 0),
                        int(baseline_totals.get("skipped") or 0),
                    )
                ),
            )
            if rounds and rounds[-1].get("stopped_reason"):
                result["stopped_reason"] = rounds[-1]["stopped_reason"]
            elif rounds and rounds[-1].get("candidate_accepted"):
                result["stopped_reason"] = (
                    "Model-selected snapshot verified and retained."
                )
            output_path.write_text(json.dumps(result, indent=2), encoding="utf-8")

        persist(baseline, retained, [])
        with _base_ref_worktree(
            Path(subject["repo_path"]), subject["base_ref"], []
        ) as context_repo:

            async def execute():
                async def run_gate(candidate):
                    return await asyncio.to_thread(verify, candidate)

                return await repair_with_agent(
                    session=ReplaySession(),
                    verification_gate=baseline,
                    generated_code_by_file=retained,
                    apply_results={},
                    problem_summary=problem,
                    max_attempts=max_attempts,
                    run_gate=run_gate,
                    log_lines=[],
                    symbol_context_repo=context_repo,
                    max_seconds=max_seconds,
                    require_tests=run_tests,
                    observe=persist,
                    mode=mode,
                    concurrency=concurrency,
                    initial_generated_sources=initial_generated_sources,
                )

            asyncio.run(execute())
        return result
    finally:
        if previous_model is None:
            os.environ.pop("DEFAULT_MODEL", None)
        else:
            os.environ["DEFAULT_MODEL"] = previous_model
