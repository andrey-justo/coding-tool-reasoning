import contextlib
import hashlib
import json
import os
from types import SimpleNamespace

import pytest

from src.experiments import repair_replay
from src.experiments.repair_replay import load_frozen_candidate, run_repair_replay
from src.service.source_identity import source_hash, sources_fingerprint


def _report(tmp_path):
    source = tmp_path / "source.json"
    source.write_text(
        json.dumps(
            {
                "run_config": {"llm": {"model": "copilot-model"}},
                "subject": {
                    "repo_path": str(tmp_path),
                    "base_ref": "base",
                    "target_files": ["A.cs"],
                },
                "mcp": {
                    "apply_results": {
                        "A.cs": {"generated_code": "class A { int Value => 1; }"}
                    },
                    "plan": {
                        "problem_description": "Native behavior without shortcuts."
                    },
                    "context": {"swe_summary": "Preserve null and empty."},
                },
            }
        ),
        encoding="utf-8",
    )
    return source


def _gate(passed=False, run_tests=True):
    return {
        "build": {"status": "pass" if passed else "fail"},
        "test": {"status": ("pass" if passed else "fail") if run_tests else "not-run"},
        "junit": {
            "totals": {
                "tests": 2,
                "passed": 2 if passed else 1,
                "failures": 0 if passed else 1,
                "errors": 0,
                "skipped": 0,
            }
        },
        "verification_scope": "full",
    }


@pytest.mark.parametrize("mode", ["loop", "tree"])
@pytest.mark.parametrize("run_tests", [False, True])
def test_replay_preserves_provenance_and_uses_model_decisions(
    tmp_path, monkeypatch, mode, run_tests
):
    source = _report(tmp_path)
    original = source.read_bytes()
    output = tmp_path / "result.json"
    monkeypatch.setenv("DEFAULT_MODEL", "previous")
    actions = iter(
        [
            {
                "action": "edit_sources",
                "rationale": "Implement the actual behavior.",
                "edits": [
                    {
                        "path": "A.cs",
                        "source_sha256": source_hash("class A { int Value => 1; }"),
                        "before": "1",
                        "after": "2",
                    }
                ],
            },
            {"action": "verify", "rationale": "Measure actual build and tests."},
            {
                "action": "finish",
                "rationale": "Checks completed.",
                "snapshot_id": 1,
                "requirements_review": "The native implementation preserves the requirements.",
            },
        ]
    )

    def decide(state):
        assert state["orchestration"]["mode"] == mode
        assert "Native behavior" in state["requirements_and_nfrs"]
        return next(actions)

    registry = SimpleNamespace(
        decide_repair_action=decide,
        review_repair_changes=lambda state: {
            "approved": True,
            "rationale": "Legitimate repair.",
            "concerns": [],
        },
        verify_testability_gate=lambda **kwargs: _gate(
            "=> 2" in kwargs["generated_code_by_file"]["A.cs"], run_tests
        ),
    )

    @contextlib.contextmanager
    def baseline(*args):
        yield tmp_path

    monkeypatch.setattr(repair_replay, "_base_ref_worktree", baseline)
    monkeypatch.setattr(repair_replay, "SweMcpToolRegistry", lambda provider: registry)
    result = run_repair_replay(
        report_path=source,
        output_path=output,
        max_attempts=1,
        mode=mode,
        run_tests=run_tests,
    )
    saved = json.loads(output.read_text(encoding="utf-8"))
    assert result["accepted"] is True
    assert saved["source_report_sha256"] == hashlib.sha256(original).hexdigest()
    assert saved["full_build_and_tests_passed"] == run_tests
    assert saved["attempts"][0]["semantic_review"]["approved"] is True
    assert source.read_bytes() == original
    assert os.environ["DEFAULT_MODEL"] == "previous"


@pytest.mark.parametrize("path", ["../A.cs", r"C:\secret.cs", "/absolute.cs"])
def test_saved_source_paths_cannot_escape_repository(path):
    with pytest.raises(ValueError):
        load_frozen_candidate(
            {
                "subject": {"target_files": [path]},
                "mcp": {"apply_results": {path: {"generated_code": "source"}}},
            }
        )


@pytest.mark.parametrize("corruption", ["parent", "files", "fingerprint"])
def test_resume_requires_provenance_complete_sources_and_exact_snapshot_hash(
    tmp_path, corruption
):
    source = _report(tmp_path)
    sources = {"A.cs": "class A {}", "Helper.cs": "class Helper {}"}
    row = {
        "attempt": 1,
        "changed": True,
        "generated_code_by_file": sources,
        "candidate_sha256": sources_fingerprint(sources),
    }
    saved = {
        "source_report_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "attempts": [row],
    }
    if corruption == "parent":
        saved["source_report_sha256"] = "wrong"
    elif corruption == "files":
        row["generated_code_by_file"] = {}
    else:
        row["candidate_sha256"] = "wrong"
    candidate = tmp_path / "candidate.json"
    candidate.write_text(json.dumps(saved), encoding="utf-8")
    with pytest.raises(ValueError):
        run_repair_replay(
            report_path=source,
            output_path=tmp_path / "result.json",
            candidate_report=candidate,
            candidate_attempt=1,
        )


def test_verify_only_resume_can_include_additional_production_sources(
    tmp_path, monkeypatch
):
    source = _report(tmp_path)
    candidate = tmp_path / "candidate.json"
    candidate.write_text(
        json.dumps(
            {
                "source_report_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                "generated_code_by_file": {
                    "A.cs": "class A {}",
                    "Helper.cs": "class Helper {}",
                },
            }
        ),
        encoding="utf-8",
    )

    @contextlib.contextmanager
    def baseline(*args):
        yield tmp_path

    monkeypatch.setattr(repair_replay, "_base_ref_worktree", baseline)
    monkeypatch.setattr(
        repair_replay,
        "SweMcpToolRegistry",
        lambda provider: SimpleNamespace(
            verify_testability_gate=lambda **kwargs: _gate(True)
        ),
    )
    result = run_repair_replay(
        report_path=source,
        output_path=tmp_path / "result.json",
        candidate_report=candidate,
        max_attempts=0,
    )
    assert result["generated_code_by_file"]["Helper.cs"] == "class Helper {}"
    assert result["attempts"] == []
