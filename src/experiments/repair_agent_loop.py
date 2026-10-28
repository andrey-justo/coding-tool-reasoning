"""Model-controlled repair with mechanical source and verification safeguards."""

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

from src.models.repair_agent import (
    EditSources,
    FinishRepair,
    ForkBranches,
    InspectSource,
    ReadSource,
    RepairAgentDecision,
    RestoreSnapshot,
    SearchSources,
    StopRepair,
    VerifySources,
)
from src.service.localizer.constants import _CODE_EXTENSIONS
from src.service.localizer.discovery import discover_repository_code_files
from src.service.source_identity import source_hash, sources_fingerprint
from src.service.ast_context_service import AstContextService
from src.models.utility_decisions import SemanticReview

logger = logging.getLogger(__name__)


def canonical_source_path(path: str, root: Path | None = None) -> str:
    parts = PurePosixPath(path.replace("\\", "/"))
    if parts.is_absolute() or PureWindowsPath(path).drive or ".." in parts.parts:
        raise ValueError(f"Source path must remain inside the repository: {path}")
    if not parts.parts or parts.suffix.lower() not in _CODE_EXTENSIONS:
        raise ValueError(f"Not a supported source path: {path}")
    if root and not (root / parts).resolve().is_relative_to(root):
        raise ValueError(f"Source path escapes the repository: {path}")
    return str(parts)


def _recent_observations(rounds: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "attempt": row["attempt"],
            "action": row["agent_action"]["action"],
            "rationale": row["agent_action"]["rationale"],
            "snapshot_id": row["snapshot_id"],
            "observation": row.get("agent_observation"),
            "error": row.get("error"),
        }
        for row in rounds[-12:]
    ]


def _full_verification_passed(
    gate: dict[str, Any], require_tests: bool, minimum_tests: int, maximum_skipped: int
) -> bool:
    build = gate.get("build") or {}
    test = gate.get("test") or {}
    if (
        gate.get("verification_scope", "full") != "full"
        or build.get("status") != "pass"
        or build.get("timed_out")
    ):
        return False
    if not require_tests:
        return True
    totals = (gate.get("junit") or {}).get("totals") or {}
    return (
        test.get("status") == "pass"
        and not test.get("timed_out")
        and int(totals.get("passed") or 0) > 0
        and int(totals.get("tests") or 0) >= minimum_tests
        and int(totals.get("tests") or 0)
        == sum(
            int(totals.get(key) or 0)
            for key in ("passed", "failures", "errors", "skipped")
        )
        and int(totals.get("skipped") or 0) <= maximum_skipped
        and not int(totals.get("failures") or 0)
        and not int(totals.get("errors") or 0)
    )


class _Sources:
    def __init__(self, root: Path | None, initial: dict[str, str]) -> None:
        self.root = root.resolve() if root else None
        paths = discover_repository_code_files(self.root) if self.root else []
        self.paths = {self.canonical(path) for path in [*paths, *initial]}
        self.originals = {
            self.canonical(path): source for path, source in initial.items()
        }
        if len(self.originals) != len(initial):
            raise ValueError("Editable sources contain duplicate canonical paths.")

    def canonical(self, path: str) -> str:
        return canonical_source_path(path, self.root)

    def read(self, path: str, current: dict[str, str], *, create: bool = False) -> str:
        path = self.canonical(path)
        if path in current:
            return current[path]
        if path in self.originals:
            return self.originals[path]
        if path not in self.paths:
            if create and self.root and not (self.root / path).exists():
                return ""
            raise ValueError(f"Source is absent from the repository inventory: {path}")
        source = self._read_repository_source(path)
        self.originals[path] = source
        return source

    def _read_repository_source(self, path: str) -> str:
        if self.root is None:
            raise ValueError(f"No repository is available for source: {path}")
        location = self.root / path
        if location.stat().st_size > 4_000_000:
            raise ValueError(f"Source exceeds the 4 MB read transport limit: {path}")
        return location.read_text(encoding="utf-8-sig")

    def baseline(self, path: str) -> str | None:
        path = self.canonical(path)
        if self.root is None:
            return None
        if not (self.root / path).exists():
            return ""
        if path not in self.paths:
            raise ValueError(
                f"Baseline source is absent from the repository inventory: {path}"
            )
        return self._read_repository_source(path)

    def search(self, query: str, current: dict[str, str]) -> dict[str, Any]:
        matches = []
        for path in sorted(self.paths | current.keys()):
            source = self.read(path, current)
            for number, line in enumerate(source.splitlines(), 1):
                if query in line:
                    if len(matches) == 80:
                        return {"matches": matches, "truncated": True}
                    matches.append({"path": path, "line": number, "text": line[:1000]})
        return {"matches": matches, "truncated": False}

    def edit(self, action: EditSources, current: dict[str, str]) -> dict[str, str]:
        staged = dict(current)
        originals: dict[str, str] = {}
        for edit in action.edits:
            path = self.canonical(edit.path)
            if path not in originals:
                originals[path] = self.read(path, current, create=edit.before == "")
            if source_hash(originals[path]) != edit.source_sha256:
                raise ValueError(f"Source hash is stale: {path}")
            before = staged.get(path, originals[path])
            if not edit.before:
                if before:
                    raise ValueError(f"Empty anchors only create new files: {path}")
                staged[path] = edit.after
            else:
                if before.count(edit.before) != 1:
                    raise ValueError(f"Replacement anchor is not unique: {path}")
                staged[path] = before.replace(edit.before, edit.after, 1)
            if not staged[path].strip():
                raise ValueError(f"Repair cannot remove all source content: {path}")
        if staged == current:
            raise ValueError("The edit transaction did not change any source.")
        return staged


async def repair_with_agent(
    *,
    session: Any,
    verification_gate: dict[str, Any],
    generated_code_by_file: dict[str, str],
    apply_results: dict[str, dict[str, Any]],
    problem_summary: str,
    max_attempts: int,
    run_gate: Any,
    log_lines: list[str],
    symbol_context_repo: Path | None = None,
    max_seconds: float = 300,
    require_tests: bool = True,
    observe: Any = None,
    mode: str = "loop",
    concurrency: int = 3,
    max_actions: int | None = None,
    minimum_tests: int = 0,
    maximum_skipped: int | None = None,
    initial_generated_sources: dict[str, str] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if mode not in {"loop", "tree"} or not 1 <= concurrency <= 8:
        raise ValueError("Invalid repair scheduling mode or concurrency budget.")
    totals = (verification_gate.get("junit") or {}).get("totals") or {}
    minimum_tests = max(minimum_tests, int(totals.get("tests") or 0))
    if maximum_skipped is None:
        maximum_skipped = int(totals.get("skipped") or 0)
    if max_attempts <= 0:
        return verification_gate, []
    sources = _Sources(symbol_context_repo, generated_code_by_file)
    initial_generated = {
        sources.canonical(path): source
        for path, source in (
            initial_generated_sources
            if initial_generated_sources is not None
            else generated_code_by_file
        ).items()
    }
    current = dict(sources.originals)
    snapshots = {0: dict(current)}
    gates = {0: verification_gate}
    snapshot_id = 0
    notes = ""
    rounds: list[dict[str, Any]] = []
    started = time.monotonic()
    edit_count = 0
    max_steps = (
        max_attempts * 8 if max_actions is None else min(max_actions, max_attempts * 8)
    )
    child_steps = 0
    for step in range(1, max_steps + 1):
        if step + child_steps > max_steps:
            break
        if time.monotonic() - started >= max_seconds:
            log_lines.append(
                "Repair agent resource time budget exhausted; input retained."
            )
            break
        response = await session.call_tool(
            "decide_repair_action",
            {
                "state": {
                    "requirements_and_nfrs": problem_summary,
                    "current_snapshot": snapshot_id,
                    "source_provenance": {
                        "baseline_available": sources.root is not None,
                        "initial_generated_paths": sorted(initial_generated),
                    },
                    "current_files": [
                        {
                            "path": path,
                            "source_sha256": source_hash(code),
                        }
                        for path, code in current.items()
                    ],
                    "verification": gates.get(snapshot_id),
                    "snapshots": [
                        {
                            "snapshot_id": key,
                            "verified": key in gates,
                            "build": (gates.get(key, {}).get("build") or {}).get(
                                "status"
                            ),
                            "test": (gates.get(key, {}).get("test") or {}).get(
                                "status"
                            ),
                        }
                        for key in snapshots
                    ],
                    "notes": notes,
                    "orchestration": {"mode": mode, "concurrency_limit": concurrency},
                    "recent_observations": _recent_observations(rounds),
                    "omitted_older_observations": max(0, len(rounds) - 12),
                    "budget": {
                        "remaining_edits": max_attempts - edit_count,
                        "remaining_actions": max_steps - step - child_steps + 1,
                        "remaining_seconds": max_seconds - (time.monotonic() - started),
                    },
                    "verification_contract": {
                        "require_tests": require_tests,
                        "minimum_tests": minimum_tests,
                        "maximum_skipped": maximum_skipped,
                    },
                }
            },
        )
        if getattr(response, "isError", False) or not response.content:
            raise RuntimeError(f"Repair decision model failed: {response.content}")
        action = RepairAgentDecision.model_validate_json(response.content[0].text).root
        notes = action.notes or notes
        row: dict[str, Any] = {
            "attempt": step + child_steps,
            "max_attempts": max_steps,
            "controller": "llm",
            "repair_mode": mode,
            "agent_action": action.model_dump(),
            "candidate_accepted": False,
            "snapshot_id": snapshot_id,
            "changed": False,
        }
        rounds.append(row)
        try:
            if isinstance(action, ReadSource):
                path = sources.canonical(action.path)
                if action.version == "baseline":
                    source = await asyncio.to_thread(sources.baseline, path)
                    if source is None:
                        raise ValueError(
                            "Baseline source is unavailable without a pinned repository."
                        )
                elif action.version == "initial_generated":
                    if path not in initial_generated:
                        raise ValueError(
                            f"No initial generated source is available: {path}"
                        )
                    source = initial_generated[path]
                else:
                    source = await asyncio.to_thread(sources.read, path, current)
                lines = source.splitlines()
                if (
                    action.start_line > max(1, len(lines))
                    or action.end_line < action.start_line
                ):
                    raise ValueError("Requested source line range does not exist.")
                end = min(action.end_line, action.start_line + 399, len(lines))
                row["agent_observation"] = {
                    "path": path,
                    "version": action.version,
                    "source_sha256": source_hash(source),
                    "start_line": action.start_line,
                    "end_line": end,
                    "source": "\n".join(lines[action.start_line - 1 : end]),
                    "total_lines": len(lines),
                    "truncated": end < min(action.end_line, len(lines)),
                }
            elif isinstance(action, SearchSources):
                row["agent_observation"] = await asyncio.to_thread(
                    sources.search, action.query, current
                )
            elif isinstance(action, InspectSource):
                path = sources.canonical(action.path)
                source = await asyncio.to_thread(sources.read, path, current)
                ast = AstContextService()
                row["agent_observation"] = {
                    "path": path,
                    "source_sha256": source_hash(source),
                    "outline": ast.describe_outline(
                        path, source, max_declarations=200
                    ).to_dict(),
                    "locations": [
                        location.to_dict()
                        for location in ast.describe_locations(
                            path, source, action.lines
                        )
                    ],
                    "evidence_kind": "syntax_tree_and_literal_source_only",
                }
            elif isinstance(action, EditSources):
                if edit_count >= max_attempts:
                    raise ValueError(
                        "Edit resource budget exhausted; verify, restore, finish or stop."
                    )
                candidate = sources.edit(action, current)
                changed = [
                    path for path in candidate if candidate[path] != current.get(path)
                ]
                changes = []
                for path in changed:
                    baseline_source = await asyncio.to_thread(sources.baseline, path)
                    changes.append(
                        {
                            "path": path,
                            "baseline_available": baseline_source is not None,
                            "baseline_source": baseline_source,
                            "initial_generated_source_sha256": (
                                source_hash(initial_generated[path])
                                if path in initial_generated
                                else None
                            ),
                            "current_source": sources.read(path, current, create=True),
                            "proposed_source": candidate[path],
                        }
                    )
                review_response = await session.call_tool(
                    "review_repair_changes",
                    {
                        "state": {
                            "issue_intent_and_nfrs": problem_summary,
                            "verification": gates.get(snapshot_id),
                            "source_provenance": {
                                "baseline_available": sources.root is not None,
                                "initial_generated_paths": sorted(initial_generated),
                            },
                            "changes": changes,
                        }
                    },
                )
                if (
                    getattr(review_response, "isError", False)
                    or not review_response.content
                ):
                    raise RuntimeError(
                        f"Repair review model failed: {review_response.content}"
                    )
                review = SemanticReview.model_validate_json(
                    review_response.content[0].text
                )
                row["semantic_review"] = review.model_dump()
                if not review.approved:
                    raise ValueError(
                        "LLM repair review rejected the edit: "
                        + "; ".join(review.concerns)
                    )
                current = candidate
                snapshot_id = len(snapshots)
                snapshots[snapshot_id] = dict(current)
                edit_count += 1
                row.update(
                    changed=True, repaired_files=changed, snapshot_id=snapshot_id
                )
                row["generated_code_by_file"] = dict(current)
                row["candidate_sha256"] = sources_fingerprint(current)
                row["agent_observation"] = {
                    "snapshot_id": snapshot_id,
                    "changed_files": changed,
                }
            elif isinstance(action, VerifySources):
                gate = await run_gate(dict(current))
                gates[snapshot_id] = gate
                observed = (gate.get("junit") or {}).get("totals") or {}
                minimum_tests = max(minimum_tests, int(observed.get("tests") or 0))
                row["agent_observation"] = gate
                row["build_status_after"] = (gate.get("build") or {}).get("status")
                row["test_status_after"] = (gate.get("test") or {}).get("status")
            elif isinstance(action, ForkBranches):
                if mode != "tree":
                    raise ValueError(
                        "fork_branches is available in tree scheduling mode."
                    )
                allocated = sum(branch.edit_budget for branch in action.branches)
                branch_actions = (max_steps - step - child_steps - 2) // len(
                    action.branches
                )
                if allocated > max_attempts - edit_count or branch_actions < 1:
                    raise ValueError(
                        "Branch allocations exceed the remaining edit/action resource budget."
                    )
                semaphore = asyncio.Semaphore(concurrency)
                parent_snapshot = snapshot_id

                async def explore(branch):
                    async with semaphore:
                        candidate = dict(current)
                        baseline_gate = gates.get(
                            parent_snapshot,
                            {
                                "build": {"status": "not-run"},
                                "test": {"status": "not-run"},
                            },
                        )
                        return await repair_with_agent(
                            session=session,
                            verification_gate=baseline_gate,
                            generated_code_by_file=candidate,
                            apply_results={},
                            problem_summary=problem_summary
                            + "\nModel-selected branch goal:\n"
                            + branch.goal,
                            max_attempts=branch.edit_budget,
                            run_gate=run_gate,
                            log_lines=[],
                            symbol_context_repo=symbol_context_repo,
                            max_seconds=max_seconds - (time.monotonic() - started),
                            require_tests=require_tests,
                            mode="loop",
                            concurrency=concurrency,
                            max_actions=branch_actions,
                            minimum_tests=minimum_tests,
                            maximum_skipped=maximum_skipped,
                            initial_generated_sources=initial_generated,
                        )

                async with asyncio.TaskGroup() as group:
                    tasks = [
                        group.create_task(explore(branch)) for branch in action.branches
                    ]
                results = [task.result() for task in tasks]
                outcomes = []
                audits = []
                for branch, (_, branch_rounds) in zip(action.branches, results):
                    mapping = {0: parent_snapshot}
                    for child in branch_rounds:
                        if child.get("changed"):
                            imported = len(snapshots)
                            snapshots[imported] = dict(child["generated_code_by_file"])
                            mapping[child["snapshot_id"]] = imported
                            edit_count += 1
                        if (
                            child["agent_action"]["action"] == "verify"
                            and child["snapshot_id"] in mapping
                            and not child.get("error")
                        ):
                            verified = child["agent_observation"]
                            gates[mapping[child["snapshot_id"]]] = verified
                            minimum_tests = max(
                                minimum_tests,
                                int(
                                    (
                                        (verified.get("junit") or {}).get("totals")
                                        or {}
                                    ).get("tests")
                                    or 0
                                ),
                            )
                    child_steps += len(branch_rounds)
                    outcomes.append(
                        {
                            "goal": branch.goal,
                            "snapshots": list(mapping.values()),
                            "snapshot_mapping": mapping,
                            "observations": _recent_observations(branch_rounds),
                        }
                    )
                    audits.append(
                        {
                            "goal": branch.goal,
                            "rounds": branch_rounds,
                            "snapshot_mapping": mapping,
                        }
                    )
                row["branch_rounds"] = audits
                row["agent_observation"] = {"branches": outcomes}
            elif isinstance(action, (RestoreSnapshot, FinishRepair)):
                if action.snapshot_id not in snapshots:
                    raise ValueError("Selected snapshot does not exist.")
                if isinstance(action, FinishRepair):
                    gate = gates.get(action.snapshot_id, {})
                    if not _full_verification_passed(
                        gate, require_tests, minimum_tests, maximum_skipped
                    ):
                        raise ValueError(
                            "Cannot finish an unverified, failing or reduced-suite snapshot."
                        )
                    current = snapshots[action.snapshot_id]
                    generated_code_by_file.clear()
                    generated_code_by_file.update(current)
                    for path, code in current.items():
                        apply_results.setdefault(path, {})["generated_code"] = code
                    row.update(candidate_accepted=True, snapshot_id=action.snapshot_id)
                    row["agent_observation"] = {"selected_snapshot": action.snapshot_id}
                    if observe:
                        observe(gate, dict(current), rounds)
                    return gate, rounds
                snapshot_id = action.snapshot_id
                current = dict(snapshots[snapshot_id])
                row["agent_observation"] = {"restored_snapshot": snapshot_id}
            elif isinstance(action, StopRepair):
                row["stopped_reason"] = action.rationale
                log_lines.append(f"Repair agent stopped: {action.rationale}")
                break
        except (ValueError, OSError, UnicodeError) as error:
            logger.warning("Repair agent action rejected: %s", error, exc_info=True)
            row["error"] = str(error)
            row["agent_observation"] = {"error": str(error)}
        if observe:
            observe(verification_gate, dict(generated_code_by_file), rounds)
    if rounds and not rounds[-1].get("stopped_reason"):
        rounds[-1]["stopped_reason"] = (
            "Repair agent resource budget exhausted; input retained."
        )
    if observe:
        observe(verification_gate, dict(generated_code_by_file), rounds)
    return verification_gate, rounds
