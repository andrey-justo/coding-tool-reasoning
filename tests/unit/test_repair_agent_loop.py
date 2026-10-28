import asyncio
import json
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest
from mcp.server.fastmcp import FastMCP
from mcp.types import CallToolResult, TextContent

from src.experiments.issue_mcp_experiment import (
    _resolve_repair_execution,
    _sanitize_build_repair_rounds,
)
from src.experiments.repair_agent_loop import repair_with_agent
from src.mcp.tools.swe_mcp_tools import SweMcpToolRegistry
from src.models.swe_config import ToolExecutionConfig
from src.service.source_identity import source_hash


ORIGINAL = {
    "A.cs": "class A { int Value => 1; }",
    "B.cs": "class B { int Value => 1; }",
}


def _action(action, **arguments):
    return {"action": action, "rationale": "Scripted model decision.", **arguments}


def _edit(path, original, before="1", after="2"):
    return {
        "path": path,
        "source_sha256": source_hash(original),
        "before": before,
        "after": after,
    }


def _finish(snapshot):
    return _action(
        "finish",
        snapshot_id=snapshot,
        requirements_review="Both implementations preserve the required native behavior.",
    )


def _gate(build="fail", test="not-run", tests=2, passed=0, skipped=0):
    return {
        "build": {"status": build, "diagnostics": [{"message": "Same diagnostic"}]},
        "test": {"status": test},
        "junit": {
            "totals": {
                "tests": tests,
                "passed": passed,
                "skipped": skipped,
                "failures": tests - passed - skipped,
                "errors": 0,
            }
        },
        "verification_scope": "full",
    }


class _Session:
    def __init__(self, actions, review=None):
        self.actions = iter(actions)
        self.states = []
        self.review_states = []
        self.review = review or {
            "approved": True,
            "rationale": "Scripted semantic approval.",
            "concerns": [],
        }

    async def call_tool(self, name, arguments):
        if name == "review_repair_changes":
            self.review_states.append(arguments["state"])
            return CallToolResult(
                content=[TextContent(type="text", text=json.dumps(self.review))]
            )
        assert (
            name == "decide_repair_action"
        ), "Agent strategy must not call heuristic repair tools."
        self.states.append(arguments["state"])
        return CallToolResult(
            content=[TextContent(type="text", text=json.dumps(next(self.actions)))]
        )


@pytest.mark.asyncio
async def test_model_controls_multifile_prerequisites_despite_unchanged_diagnostics():
    current = dict(ORIGINAL)
    changed_b = ORIGINAL["B.cs"].replace("1", "2")
    session = _Session(
        [
            _action("read_source", path="A.cs"),
            _action(
                "edit_sources",
                edits=[_edit(path, source) for path, source in ORIGINAL.items()],
            ),
            _action("verify"),
            _action("edit_sources", edits=[_edit("B.cs", changed_b, "2", "3")]),
            _action("verify"),
            _finish(2),
        ]
    )
    results = iter([_gate(), _gate("pass", "pass", passed=2)])
    observed = []

    async def verify(candidate):
        assert current == ORIGINAL, "Provisional edits must not be published."
        observed.append(candidate)
        return next(results)

    gate, rounds = await repair_with_agent(
        session=session,
        verification_gate=_gate(),
        generated_code_by_file=current,
        apply_results={},
        problem_summary="Native behavior and Reliability.",
        max_attempts=3,
        run_gate=verify,
        log_lines=[],
    )
    assert gate["build"]["status"] == "pass"
    assert len(observed) == 2
    assert current["A.cs"].endswith("2; }")
    assert current["B.cs"].endswith("3; }")
    assert (
        session.states[0]["requirements_and_nfrs"] == "Native behavior and Reliability."
    )
    assert rounds[-1]["candidate_accepted"] is True
    assert _sanitize_build_repair_rounds(rounds)[1]["generated_code_by_file"][
        "A.cs"
    ].endswith("2; }")
    assert (
        _sanitize_build_repair_rounds(rounds)[0]["agent_action"]["action"]
        == "read_source"
    )


@pytest.mark.asyncio
async def test_model_selects_an_earlier_verified_snapshot_not_the_latest_edit():
    current = dict(ORIGINAL)
    first = ORIGINAL["A.cs"].replace("1", "2")
    session = _Session(
        [
            _action("edit_sources", edits=[_edit("A.cs", ORIGINAL["A.cs"])]),
            _action("verify"),
            _action("edit_sources", edits=[_edit("A.cs", first, "2", "3")]),
            _action("restore_snapshot", snapshot_id=1),
            _finish(1),
        ]
    )

    async def verify(candidate):
        return _gate("pass", "pass", passed=2)

    _, rounds = await repair_with_agent(
        session=session,
        verification_gate=_gate(),
        generated_code_by_file=current,
        apply_results={},
        problem_summary="Preserve requirements.",
        max_attempts=2,
        run_gate=verify,
        log_lines=[],
    )
    assert current["A.cs"] == first
    assert rounds[-1]["snapshot_id"] == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("violation", ["stale", "test", "escape", "project"])
async def test_invalid_multifile_transaction_is_atomic_and_errors_reach_model(
    violation,
):
    current = {**ORIGINAL, "tests/Fixture.cs": "class Fixture {}"}
    bad = _edit("B.cs", ORIGINAL["B.cs"])
    if violation == "stale":
        bad["source_sha256"] = "0" * 64
    elif violation == "test":
        bad = _edit(
            "tests/Fixture.cs", current["tests/Fixture.cs"], "Fixture", "WeakFixture"
        )
    elif violation == "project":
        current["App.csproj"] = '<Project Sdk="Microsoft.NET.Sdk" />'
        bad = _edit("App.csproj", current["App.csproj"], "Sdk", "DisabledSdk")
    else:
        bad["path"] = "../B.cs"
    session = _Session(
        [
            _action("edit_sources", edits=[_edit("A.cs", ORIGINAL["A.cs"]), bad]),
            _action("stop"),
        ]
    )
    if violation in {"test", "project"}:
        session.review = {
            "approved": False,
            "rationale": "The proposed change weakens validation.",
            "concerns": ["Preserve the test and verification behavior."],
        }
    baseline = dict(current)
    _, rounds = await repair_with_agent(
        session=session,
        verification_gate=_gate(),
        generated_code_by_file=current,
        apply_results={},
        problem_summary="Requirements",
        max_attempts=1,
        run_gate=None,
        log_lines=[],
    )
    assert current == baseline
    assert rounds[0]["error"]
    assert session.states[1]["recent_observations"][0]["error"] == rounds[0]["error"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "candidate",
    [
        {**_gate("pass", "pass", passed=2), "verification_scope": "focused"},
        _gate("pass", "pass", tests=1, passed=1),
        _gate("pass", "pass", passed=1, skipped=1),
        {
            **_gate("pass", "pass", passed=2),
            "test": {"status": "pass", "timed_out": True},
        },
    ],
)
async def test_model_cannot_finish_focused_reduced_skipped_or_timed_out_verification(
    candidate,
):
    current = dict(ORIGINAL)
    session = _Session(
        [
            _action("edit_sources", edits=[_edit("A.cs", ORIGINAL["A.cs"])]),
            _action("verify"),
            _finish(1),
            _action("stop"),
        ]
    )

    async def verify(sources):
        return candidate

    gate, rounds = await repair_with_agent(
        session=session,
        verification_gate=_gate(),
        generated_code_by_file=current,
        apply_results={},
        problem_summary="Requirements",
        max_attempts=1,
        run_gate=verify,
        log_lines=[],
    )
    assert gate["build"]["status"] == "fail"
    assert current == ORIGINAL
    assert "Cannot finish" in rounds[-2]["error"]


@pytest.mark.asyncio
async def test_behavioral_agent_can_expand_production_scope_and_create_a_helper(
    tmp_path,
):
    (tmp_path / "Library.cs").write_text(
        "class Library { int Value => 1; }", encoding="utf-8"
    )
    (tmp_path / "App.csproj").write_text(
        '<Project Sdk="Microsoft.NET.Sdk" />', encoding="utf-8"
    )
    session = _Session(
        [
            _action("read_source", path="App.csproj"),
            _action("search_sources", query="Library"),
            _action("read_source", path="Library.cs"),
            _action(
                "edit_sources",
                edits=[
                    _edit("Library.cs", "class Library { int Value => 1; }"),
                    _edit("NewHelper.cs", "", "", "class NewHelper {}"),
                ],
            ),
            _action("verify"),
            _finish(1),
        ]
    )
    current = dict(ORIGINAL)
    apply_results = {}

    async def verify(candidate):
        assert "Library.cs" in candidate and "NewHelper.cs" in candidate
        return _gate("pass", "pass", passed=2)

    gate, _ = await repair_with_agent(
        session=session,
        verification_gate=_gate("pass", "fail"),
        generated_code_by_file=current,
        apply_results=apply_results,
        problem_summary="Native behavior.",
        max_attempts=1,
        run_gate=verify,
        log_lines=[],
        symbol_context_repo=tmp_path,
    )
    assert gate["test"]["status"] == "pass"
    assert current["Library.cs"].endswith("2; }")
    assert apply_results["NewHelper.cs"]["generated_code"] == "class NewHelper {}"
    assert not (tmp_path / "NewHelper.cs").exists()
    assert (tmp_path / "Library.cs").read_text(encoding="utf-8").endswith("1; }")


@pytest.mark.asyncio
async def test_unverified_finish_does_not_publish_and_stop_is_observed():
    current = dict(ORIGINAL)
    session = _Session([_finish(0), _action("stop")])
    observations = []
    await repair_with_agent(
        session=session,
        verification_gate=_gate(),
        generated_code_by_file=current,
        apply_results={},
        problem_summary="Requirements",
        max_attempts=1,
        run_gate=None,
        log_lines=[],
        observe=lambda gate, code, rounds: observations.append(list(rounds)),
    )
    assert current == ORIGINAL
    assert observations[-1][-1]["agent_action"]["action"] == "stop"


@pytest.mark.asyncio
async def test_agent_has_no_legacy_edit_count_or_declaration_size_restriction():
    current = {f"File{i}.cs": f"class C{i} {{ int Value => 1; }}" for i in range(7)}
    edits = [
        _edit(path, source, before="Value => 1", after="Value => 2" + " " * 9000)
        for path, source in current.items()
    ]
    assert len(edits) > 6 and sum(len(edit["after"]) for edit in edits) > 24000
    session = _Session(
        [_action("edit_sources", edits=edits), _action("verify"), _finish(1)]
    )

    async def verify(candidate):
        assert all("2" + " " * 9000 in source for source in candidate.values())
        return _gate("pass", "pass", passed=2)

    gate, _ = await repair_with_agent(
        session=session,
        verification_gate=_gate(),
        generated_code_by_file=current,
        apply_results={},
        problem_summary="Requirements",
        max_attempts=1,
        run_gate=verify,
        log_lines=[],
    )
    assert gate["build"]["status"] == "pass"


@pytest.mark.asyncio
async def test_resource_budget_bounds_actions_without_publishing_a_partial_candidate():
    session = _Session([_action("read_source", path="A.cs")] * 8)
    current = dict(ORIGINAL)
    _, rounds = await repair_with_agent(
        session=session,
        verification_gate=_gate(),
        generated_code_by_file=current,
        apply_results={},
        problem_summary="Requirements",
        max_attempts=1,
        run_gate=None,
        log_lines=[],
    )
    assert len(session.states) == 8
    assert current == ORIGINAL
    assert "resource budget exhausted" in rounds[-1]["stopped_reason"]


@pytest.mark.asyncio
async def test_registered_decision_tool_uses_injected_model_and_external_prompt():
    prompts = []

    class Client:
        def chat(self, prompt):
            prompts.append(prompt)
            return json.dumps(_action("stop"))

    server = FastMCP("agent-test")
    registry = SweMcpToolRegistry(lambda: SimpleNamespace(), llm_client_cls=Client)
    registry.register_on_mcp(server)
    await server.call_tool(
        "decide_repair_action", {"state": {"requirements": "Native collections"}}
    )
    assert len(prompts) == 1
    assert "You control the repair" in prompts[0]
    assert "Native collections" in prompts[0]
    assert ToolExecutionConfig().repair_mode == "loop"


class _TreeSession(_Session):
    def __init__(self, parent_actions, children):
        super().__init__(parent_actions)
        self.children = {goal: _Session(actions) for goal, actions in children.items()}

    async def call_tool(self, name, arguments):
        state = arguments["state"]
        if name == "decide_repair_action" and state["orchestration"]["mode"] == "loop":
            goal = state["requirements_and_nfrs"].rsplit(
                "\nModel-selected branch goal:\n", 1
            )[-1]
            return await self.children[goal].call_tool(name, arguments)
        return await super().call_tool(name, arguments)


def _fork(*goals):
    return {
        "action": "fork_branches",
        "rationale": "Compare alternative implementations.",
        "branches": [{"goal": goal, "edit_budget": 1} for goal in goals],
    }


def _child(edit):
    return [
        {
            "action": "edit_sources",
            "rationale": "Implement this hypothesis.",
            "edits": [edit],
        },
        {"action": "verify", "rationale": "Collect real verification observations."},
        {
            "action": "stop",
            "rationale": "Return this provisional checkpoint to the parent.",
        },
    ]


@pytest.mark.asyncio
async def test_parallel_tree_keeps_siblings_isolated_and_model_selects_checkpoint():
    current = dict(ORIGINAL)
    session = _TreeSession(
        [_fork("first", "second", "third"), _finish(1)],
        {
            "first": _child(_edit("A.cs", ORIGINAL["A.cs"], after="2")),
            "second": _child(_edit("B.cs", ORIGINAL["B.cs"], after="3")),
            "third": _child(_edit("A.cs", ORIGINAL["A.cs"], after="4")),
        },
    )
    ready = asyncio.Event()
    active = 0
    peak = 0
    candidates = []

    async def verify(candidate):
        nonlocal active, peak
        candidates.append(dict(candidate))
        active += 1
        peak = max(peak, active)
        if active == 2:
            ready.set()
        await asyncio.wait_for(ready.wait(), timeout=2)
        active -= 1
        return _gate("pass", "pass", passed=2)

    gate, rounds = await repair_with_agent(
        session=session,
        verification_gate=_gate(),
        generated_code_by_file=current,
        apply_results={},
        problem_summary="Requirements remain mandatory.",
        max_attempts=3,
        run_gate=verify,
        log_lines=[],
        mode="tree",
        concurrency=2,
    )
    assert peak == 2
    assert len(candidates) == 3
    assert candidates[0]["B.cs"] == ORIGINAL["B.cs"]
    assert candidates[1]["A.cs"] == ORIGINAL["A.cs"]
    assert current == candidates[0]
    assert gate["test"]["status"] == "pass"
    assert rounds[-1]["snapshot_id"] == 1
    assert len(rounds[0]["branch_rounds"]) == 3
    assert session.states[-1]["budget"]["remaining_edits"] == 0
    assert len(session.states[-1]["snapshots"]) == 4


@pytest.mark.asyncio
async def test_parent_checks_suite_floor_across_all_provisional_branches():
    current = dict(ORIGINAL)
    session = _TreeSession(
        [
            _fork("larger", "smaller"),
            _finish(2),
            {"action": "stop", "rationale": "Investigate the missing tests."},
        ],
        {
            "larger": _child(_edit("A.cs", ORIGINAL["A.cs"], after="2")),
            "smaller": _child(_edit("B.cs", ORIGINAL["B.cs"], after="3")),
        },
    )

    async def verify(candidate):
        result = _gate("pass", "pass", passed=2)
        if candidate["A.cs"] != ORIGINAL["A.cs"]:
            result["junit"]["totals"].update(tests=5, passed=5)
        return result

    _, rounds = await repair_with_agent(
        session=session,
        verification_gate=_gate(),
        generated_code_by_file=current,
        apply_results={},
        problem_summary="Keep the full suite.",
        max_attempts=2,
        run_gate=verify,
        log_lines=[],
        mode="tree",
    )
    assert current == ORIGINAL
    assert "reduced-suite" in rounds[1]["error"]
    assert session.states[-1]["verification_contract"]["minimum_tests"] == 5


@pytest.mark.asyncio
@pytest.mark.parametrize("mode,max_attempts", [("loop", 2), ("tree", 1)])
async def test_forks_obey_mode_and_shared_resource_budget(mode, max_attempts):
    session = _Session(
        [
            _fork("first", "second"),
            {"action": "stop", "rationale": "Cannot schedule these branches."},
        ]
    )
    _, rounds = await repair_with_agent(
        session=session,
        verification_gate=_gate(),
        generated_code_by_file=dict(ORIGINAL),
        apply_results={},
        problem_summary="Preserve requirements.",
        max_attempts=max_attempts,
        run_gate=None,
        log_lines=[],
        mode=mode,
    )
    assert rounds[0]["error"]
    assert "branch_rounds" not in rounds[0]


@pytest.mark.asyncio
async def test_parent_can_resume_and_fork_provisional_child_again():
    first = ORIGINAL["A.cs"].replace("1", "2")
    session = _TreeSession(
        [
            _fork("first", "second"),
            _action("restore_snapshot", snapshot_id=1),
            _fork("deeper", "alternative"),
            _finish(3),
        ],
        {
            "first": _child(_edit("A.cs", ORIGINAL["A.cs"], after="2")),
            "second": _child(_edit("B.cs", ORIGINAL["B.cs"], after="3")),
            "deeper": _child(_edit("A.cs", first, before="2", after="4")),
            "alternative": _child(_edit("B.cs", ORIGINAL["B.cs"], after="5")),
        },
    )
    current = dict(ORIGINAL)

    async def verify(candidate):
        return _gate("pass", "pass", passed=2)

    _, rounds = await repair_with_agent(
        session=session,
        verification_gate=_gate(),
        generated_code_by_file=current,
        apply_results={},
        problem_summary="Complete the requirements.",
        max_attempts=4,
        run_gate=verify,
        log_lines=[],
        mode="tree",
    )
    assert current["A.cs"] == ORIGINAL["A.cs"].replace("1", "4")
    assert current["B.cs"] == ORIGINAL["B.cs"]
    assert rounds[-1]["snapshot_id"] == 3
    assert session.states[-1]["budget"]["remaining_edits"] == 0


@pytest.mark.asyncio
async def test_successful_initial_build_still_leaves_requirement_review_to_model():
    session = _Session([_finish(0)])
    _, rounds = await repair_with_agent(
        session=session,
        verification_gate=_gate("pass", "pass", passed=2),
        generated_code_by_file=dict(ORIGINAL),
        apply_results={},
        problem_summary="Review native behavior, not only compilation.",
        max_attempts=1,
        run_gate=None,
        log_lines=[],
    )
    assert len(session.states) == 1
    assert rounds[0]["candidate_accepted"] is True


@pytest.mark.asyncio
async def test_model_patch_is_checked_by_actual_dotnet_compiler(tmp_path):
    dotnet = shutil.which("dotnet")
    if not dotnet:
        pytest.skip("A .NET SDK is required for compiler integration.")
    version = subprocess.run(
        [dotnet, "--version"], capture_output=True, text=True, check=True
    ).stdout.strip()
    framework = f"net{int(version.split('.')[0])}.0"
    project = f'<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><TargetFramework>{framework}</TargetFramework></PropertyGroup></Project>'
    original = "public class Example { public static int Value() => Missing(); }"
    current = {"Example.cs": original}

    def compile_sources(candidate):
        with tempfile.TemporaryDirectory(prefix="model-repair-") as directory:
            root = Path(directory)
            (root / "Example.csproj").write_text(project, encoding="utf-8")
            for path, code in candidate.items():
                (root / path).write_text(code, encoding="utf-8")
            result = subprocess.run(
                [dotnet, "build", "--nologo", "--verbosity", "quiet"],
                cwd=root,
                capture_output=True,
                text=True,
                timeout=90,
            )
            return {
                "build": {
                    "status": "pass" if result.returncode == 0 else "fail",
                    "output": result.stdout + result.stderr,
                },
                "test": {"status": "not-run"},
                "verification_scope": "full",
            }

    baseline = await asyncio.to_thread(compile_sources, current)
    assert baseline["build"]["status"] == "fail"
    assert "CS0103" in baseline["build"]["output"]
    session = _Session(
        [
            _action(
                "edit_sources", edits=[_edit("Example.cs", original, "Missing()", "42")]
            ),
            _action("verify"),
            _finish(1),
        ]
    )

    async def verify(candidate):
        return await asyncio.to_thread(compile_sources, candidate)

    gate, _ = await repair_with_agent(
        session=session,
        verification_gate=baseline,
        generated_code_by_file=current,
        apply_results={},
        problem_summary="Return the required value.",
        max_attempts=1,
        run_gate=verify,
        log_lines=[],
        require_tests=False,
    )
    assert gate["build"]["status"] == "pass"
    assert "=> 42;" in current["Example.cs"]


def test_repair_execution_preserves_yaml_settings_and_validates_cli_overrides():
    config = ToolExecutionConfig(
        repair_mode="tree", repair_concurrency=2, max_build_repair_attempts=7
    )
    inherited = _resolve_repair_execution(SimpleNamespace(), config)
    assert inherited == config
    override = _resolve_repair_execution(
        SimpleNamespace(repair_mode="loop", max_build_repair_attempts=3), config
    )
    assert override.repair_mode == "loop"
    assert override.max_build_repair_attempts == 3
    assert override.repair_concurrency == 2
    with pytest.raises(ValueError):
        _resolve_repair_execution(SimpleNamespace(repair_concurrency=0), config)
    with pytest.raises(ValueError):
        ToolExecutionConfig(auto_repair_strategy="deterministic")


@pytest.mark.asyncio
@pytest.mark.parametrize("tool_name", ["decide_repair_action", "review_repair_changes"])
async def test_registered_model_tools_do_not_block_parallel_mcp_requests(
    monkeypatch, tool_name
):
    rendezvous = threading.Barrier(2)

    def model_call(state):
        rendezvous.wait(timeout=3)
        return {"branch": state["branch"]}

    server = FastMCP("parallel-model-test")
    registry = SweMcpToolRegistry(lambda: SimpleNamespace())
    monkeypatch.setattr(registry, tool_name, model_call)
    registry.register_on_mcp(server)
    results = await asyncio.gather(
        *(
            server.call_tool(tool_name, {"state": {"branch": index}})
            for index in range(2)
        )
    )
    assert len(results) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("existing_file", [True, False])
async def test_generated_fixture_setup_can_be_repaired_without_changing_checks(
    tmp_path, existing_file
):
    baseline = (
        "class ExistingChecks { void Check() { Assert.Equal(42, Actual()); } }\n"
        if existing_file
        else ""
    )
    generated = (
        baseline
        + 'class GeneratedCase { string Sample = "[AkkaSerializable] record Reading(int Value);"; void Check() { Assert.Empty(RunGenerator(Sample)); } }'
    )
    if existing_file:
        (tmp_path / "Fixture.cs").write_text(baseline, encoding="utf-8")
    current = {"Fixture.cs": generated}
    session = _Session(
        [
            _action("read_source", path="Fixture.cs", version="baseline"),
            _action("read_source", path="Fixture.cs", version="initial_generated"),
            _action(
                "edit_sources",
                edits=[
                    _edit(
                        "Fixture.cs",
                        generated,
                        "[AkkaSerializable]",
                        '[AkkaSerializable(Manifest=\\"reading\\")]',
                    )
                ],
            ),
            _action("verify"),
            _finish(1),
        ]
    )

    async def verify(candidate):
        assert candidate["Fixture.cs"].startswith(baseline)
        assert "Assert.Empty(RunGenerator(Sample));" in candidate["Fixture.cs"]
        assert 'Manifest=\\"reading\\"' in candidate["Fixture.cs"]
        return _gate("pass", "pass", passed=2)

    _, rounds = await repair_with_agent(
        session=session,
        verification_gate=_gate(),
        generated_code_by_file=current,
        apply_results={},
        problem_summary="Support the required shapes without weakening checks.",
        max_attempts=1,
        run_gate=verify,
        log_lines=[],
        symbol_context_repo=tmp_path,
    )
    change = session.review_states[0]["changes"][0]
    assert change["baseline_available"] is True
    assert change["baseline_source"] == baseline
    assert change["current_source"] == generated
    assert change["initial_generated_source_sha256"] == source_hash(generated)
    assert rounds[0]["agent_observation"]["source"] == baseline.rstrip("\n")
    assert rounds[1]["agent_observation"]["source"] == generated
    assert rounds[-1]["candidate_accepted"] is True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "before,after",
    [
        ("Assert.Equal(42, Actual());", "Assert.True(true);"),
        ("void Check() { Assert.Equal(42, Actual()); }", ""),
        ("[Fact]", '[Fact(Skip = "Ignore failure")]'),
    ],
)
async def test_baseline_test_weakening_is_rejected_with_original_evidence(
    tmp_path, before, after
):
    baseline = (
        "class ExistingChecks { [Fact] void Check() { Assert.Equal(42, Actual()); } }\n"
    )
    generated = baseline + "class AddedFixture {}"
    (tmp_path / "Fixture.cs").write_text(baseline, encoding="utf-8")
    current = {"Fixture.cs": generated}
    session = _Session(
        [
            _action(
                "edit_sources", edits=[_edit("Fixture.cs", generated, before, after)]
            ),
            _action("stop"),
        ],
        review={
            "approved": False,
            "rationale": "Baseline verification is weakened.",
            "concerns": ["Preserve baseline assertions, cases and execution."],
        },
    )
    _, rounds = await repair_with_agent(
        session=session,
        verification_gate=_gate(),
        generated_code_by_file=current,
        apply_results={},
        problem_summary="Preserve acceptance behavior.",
        max_attempts=1,
        run_gate=None,
        log_lines=[],
        symbol_context_repo=tmp_path,
    )
    assert session.review_states[0]["changes"][0]["baseline_source"] == baseline
    assert current["Fixture.cs"] == generated
    assert rounds[0]["semantic_review"]["approved"] is False
    assert rounds[0]["changed"] is False


@pytest.mark.asyncio
async def test_parallel_children_keep_initial_generation_provenance_after_parent_edit(
    tmp_path,
):
    baseline = "class ExistingChecks {}"
    generated = baseline + 'class Fixture { string Metadata = "[Attribute]"; }'
    intermediate = "using System;\n" + generated
    (tmp_path / "Fixture.cs").write_text(baseline, encoding="utf-8")
    current = {"Fixture.cs": generated, "A.cs": ORIGINAL["A.cs"]}
    session = _TreeSession(
        [
            _action(
                "edit_sources",
                edits=[_edit("Fixture.cs", generated, generated, intermediate)],
            ),
            _fork("fixture", "implementation"),
            _finish(2),
        ],
        {
            "fixture": _child(
                _edit(
                    "Fixture.cs", intermediate, "[Attribute]", "[Attribute(Value=42)]"
                )
            ),
            "implementation": _child(_edit("A.cs", ORIGINAL["A.cs"], after="3")),
        },
    )

    async def verify(candidate):
        return _gate("pass", "pass", passed=2)

    _, rounds = await repair_with_agent(
        session=session,
        verification_gate=_gate(),
        generated_code_by_file=current,
        apply_results={},
        problem_summary="Repair generated setup, not baseline checks.",
        max_attempts=3,
        run_gate=verify,
        log_lines=[],
        symbol_context_repo=tmp_path,
        mode="tree",
    )
    fixture_reviews = [
        change
        for state in session.review_states
        for change in state["changes"]
        if change["path"] == "Fixture.cs"
    ]
    assert len(fixture_reviews) == 2
    assert all(change["baseline_source"] == baseline for change in fixture_reviews)
    assert all(
        change["initial_generated_source_sha256"] == source_hash(generated)
        for change in fixture_reviews
    )
    assert fixture_reviews[1]["current_source"] == intermediate
    assert "[Attribute(Value=42)]" in current["Fixture.cs"]
    assert rounds[-1]["candidate_accepted"] is True


@pytest.mark.asyncio
async def test_missing_baseline_is_explicit_not_assumed_generated():
    session = _Session(
        [
            _action("read_source", path="A.cs", version="baseline"),
            _action("edit_sources", edits=[_edit("A.cs", ORIGINAL["A.cs"])]),
            _action("stop"),
        ]
    )
    _, rounds = await repair_with_agent(
        session=session,
        verification_gate=_gate(),
        generated_code_by_file=dict(ORIGINAL),
        apply_results={},
        problem_summary="Inspect provenance.",
        max_attempts=1,
        run_gate=None,
        log_lines=[],
    )
    assert "Baseline source is unavailable" in rounds[0]["error"]
    change = session.review_states[0]["changes"][0]
    assert change["baseline_available"] is False
    assert change["baseline_source"] is None
