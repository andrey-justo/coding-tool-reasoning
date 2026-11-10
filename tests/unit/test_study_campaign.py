from __future__ import annotations

import csv
import json
import sqlite3
import subprocess
import threading
import time
from collections import Counter
from copy import deepcopy
from pathlib import Path
from unittest.mock import Mock

import pytest
import yaml
from pydantic import ValidationError

from src import main as main_cli
from src.evaluation.metrics.structural import (
    canonical_hash,
    compare_structural_metrics,
    source_hash,
)
from src.experiments import campaign_runner
from src.experiments.campaign_plan import (
    WORKSPACE,
    build_campaign_plan,
    file_hash,
    verify_plan_inputs,
)
from src.experiments.campaign_runner import (
    TrialResult,
    WorkerCleanupError,
    WorkerResult,
    _frozen_bytes,
    _validate_report,
    campaign_status,
    export_campaign,
    initialize_ledger,
    ledger_lock,
    load_plan,
    materialize_study,
    recover_campaign,
    resolve_execution_config,
    run_campaign,
)
from src.models.study_campaign import StudyCampaign
from src.models.swe_config import SweMcpConfig
from tests.unit.test_structural_metrics import synthetic_input


@pytest.fixture(scope="module")
def configured_plan():
    return build_campaign_plan(WORKSPACE / "experiments" / "campaign.yaml")


def freeze(plan):
    plan.plan_sha256 = canonical_hash(
        plan.model_dump(mode="json", exclude={"plan_sha256"})
    )
    return plan


@pytest.fixture
def ready_plan(configured_plan, tmp_path):
    plan = configured_plan.model_copy(deep=True)
    plan.campaign.studies = [
        study for study in plan.campaign.studies if study.id == "strictness"
    ]
    plan.jobs = [job for job in plan.jobs if job.study == "strictness"][:6]
    ids = {job.id for job in plan.jobs}
    plan.pairs = [
        pair for pair in plan.pairs if {pair.control_job, pair.treatment_job} <= ids
    ]
    for index, job in enumerate(plan.jobs):
        job.blockers = []
        job.repo_path = str(tmp_path / f"repository-{index // 3}")
        job.repository_key = job.repo_path
    plan.artifact_root = str(tmp_path / "artifacts")
    plan.ledger_path = str(tmp_path / "ledger.sqlite")
    plan.campaign.execution.max_parallel_trials = 2
    source = tmp_path / "frozen-input.txt"
    source.write_text("test-only frozen input", encoding="utf-8")
    plan.inputs = {str(source): file_hash(source)}
    plan.input_trees = {}
    return freeze(plan)


def successful_result(*, gate=True, measured=True, identity="b" * 64):
    return WorkerResult(
        return_code=0,
        result=TrialResult(
            gate_passed=gate,
            m1_available=measured,
            delta_struct=0.5 if measured else None,
            protocol_sha256="a" * 64 if measured else None,
            measurement_identity=identity if measured else None,
            issue_context_sha256="c" * 64,
            verdict="acceptable",
            sampling_control_status="unsupported",
        ),
    )


def successful_worker(job, plan, directory, execution_id, stop):
    directory.mkdir(parents=True, exist_ok=False)
    return successful_result()


def ledger_rows(ledger, table):
    with sqlite3.connect(ledger) as connection:
        connection.row_factory = sqlite3.Row
        return [dict(row) for row in connection.execute(f"SELECT * FROM {table}")]


def temporary_manifest(plan, tmp_path, change):
    data = plan.campaign.model_dump(mode="json")
    data["config_root"] = str(WORKSPACE)
    change(data)
    path = tmp_path / "campaign.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return path


def test_real_campaign_counts_and_reused_medium_jobs(configured_plan):
    assert len(configured_plan.jobs) == 810
    assert len(configured_plan.pairs) == 420
    assert Counter(job.study for job in configured_plan.jobs) == {
        "effectiveness": 60,
        "strictness": 90,
        "robustness": 600,
        "legacy-effectiveness": 60,
    }
    strict = [pair for pair in configured_plan.pairs if pair.study == "strictness"]
    assert Counter(pair.comparison for pair in strict) == {
        "low-vs-medium": 30,
        "high-vs-medium": 30,
    }
    assert len({pair.control_job for pair in strict}) == 30
    assert len({job.id for job in configured_plan.jobs}) == 810
    assert len({pair.id for pair in configured_plan.pairs}) == 420
    assert all(job.blockers for job in configured_plan.jobs)
    assert len(configured_plan.registry_audit) == 72
    assert sum(bool(row["errors"]) for row in configured_plan.registry_audit) == 53
    assert (
        len(
            {
                job.slot
                for job in configured_plan.jobs
                if job.study == "effectiveness" and job.subject_id
            }
        )
        == 20
    )
    assert (
        len(
            {
                job.slot
                for job in configured_plan.jobs
                if job.study == "legacy-effectiveness" and job.subject_id
            }
        )
        == 6
    )
    assert (
        len(
            {
                job.subject_id
                for job in configured_plan.jobs
                if job.study == "effectiveness" and job.subject_id
            }
        )
        == 10
    )
    assert {
        job.runtime.judging.strictness
        for job in configured_plan.jobs
        if job.study == "strictness"
    } == {0.2, 0.5, 0.8}
    verify_plan_inputs(configured_plan)


def test_real_csv_references_shared_issue_configs():
    with (WORKSPACE / "data" / "subjects" / "experiment_runs.csv").open(
        newline="", encoding="utf-8-sig"
    ) as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 40
    references = Counter(row["experiment_config"] for row in rows)
    assert len(references) == 20
    assert set(references.values()) == {2}
    for row in rows:
        path = WORKSPACE / row["experiment_config"].replace("\\", "/")
        binding = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert binding["subject_id"] == row["subject_id"]
        assert (
            binding["issue_url"]
            == f"https://github.com/{row['repo_owner']}/{row['repo_name']}/issues/{row['issue_id']}"
        )
        assert binding["base_commit"] is None
        assert binding["ai_use_approved"] is False


def test_plan_expansion_is_deterministic(configured_plan):
    repeated = build_campaign_plan(Path(configured_plan.manifest_path))
    assert repeated.model_dump() == configured_plan.model_dump()


@pytest.mark.parametrize(
    "change, message",
    [
        (lambda data: data["model"].update(seed=1), "CopilotSDK"),
        (lambda data: data.update(mode="confirmatory"), "confirmatory"),
        (lambda data: data["studies"][0].update(cohort="unknown"), "unknown cohort"),
        (
            lambda data: data["studies"][0]["conditions"].append(
                data["studies"][0]["conditions"][0]
            ),
            "unique",
        ),
        (
            lambda data: data["studies"][0]["comparisons"][0].update(control="unknown"),
            "distinct declared",
        ),
        (
            lambda data: data["studies"][0]["conditions"][0].update(strictness=0.5),
            "baseline parameter",
        ),
        (
            lambda data: data["cohorts"]["main"]["bindings"].update(unknown={}),
            "unknown task slots",
        ),
    ],
)
def test_manifest_validation(configured_plan, change, message):
    data = configured_plan.campaign.model_dump(mode="json")
    change(data)
    with pytest.raises(ValidationError, match=message):
        StudyCampaign.model_validate(data)


def test_confirmatory_requires_sampling_controls(configured_plan):
    data = configured_plan.campaign.model_dump(mode="json")
    data.update(mode="confirmatory")
    data["model"] = {"alias": "test", "provider": "LocalAI"}
    with pytest.raises(ValidationError, match="explicitly registered"):
        StudyCampaign.model_validate(data)


def test_cannot_freeze_an_unused_models_file(configured_plan, tmp_path):
    path = temporary_manifest(
        configured_plan,
        tmp_path,
        lambda data: data.update(available_models="not-used.yaml"),
    )
    with pytest.raises(ValueError, match="application-root"):
        build_campaign_plan(path)


def test_duplicate_tasks_require_repetitions(configured_plan, tmp_path):
    def change(data):
        data["cohorts"]["main"]["bindings"]["set01-task02"] = {
            "subject_id": "S001",
            "issue_url": "https://github.com/dotnet/aspnetcore/issues/131001",
        }
        data["cohorts"]["main"]["bindings"]["set01-task01"] = {
            "subject_id": "S001",
            "issue_url": "https://github.com/dotnet/aspnetcore/issues/131001",
        }

    path = temporary_manifest(configured_plan, tmp_path, change)
    with pytest.raises(ValueError, match="Duplicate cohort tasks"):
        build_campaign_plan(path)


def test_ledger_override_is_frozen_and_reusable(ready_plan, tmp_path):
    override = tmp_path / "alternate.sqlite"
    assert initialize_ledger(ready_plan, override) == override
    assert initialize_ledger(ready_plan, override) == override
    assert not Path(ready_plan.ledger_path).exists()
    with sqlite3.connect(override) as connection:
        connection.row_factory = sqlite3.Row
        frozen = load_plan(connection)
    assert frozen.ledger_path == str(override)
    verify_plan_inputs(frozen)
    run_campaign(override, max_trials=1, worker=successful_worker)
    assert campaign_status(override)["execution_statuses"]["completed"] == 1


def test_ledger_rejects_changed_plan(ready_plan):
    ledger = initialize_ledger(ready_plan)
    ready_plan.jobs[0].runtime.judging.strictness = 0.42
    freeze(ready_plan)
    with pytest.raises(ValueError, match="different frozen plan"):
        initialize_ledger(ready_plan)
    assert len(ledger_rows(ledger, "jobs")) == 6


def test_input_and_plan_drift_are_rejected(ready_plan):
    source = Path(next(iter(ready_plan.inputs)))
    assert _frozen_bytes(ready_plan, source) == source.read_bytes()
    source.write_text("drift", encoding="utf-8")
    with pytest.raises(ValueError, match="Frozen campaign input"):
        verify_plan_inputs(ready_plan)
    with pytest.raises(ValueError, match="Frozen input changed"):
        _frozen_bytes(ready_plan, source)
    ready_plan.jobs[0].condition = "tampered"
    with pytest.raises(ValueError, match="SHA-256"):
        verify_plan_inputs(ready_plan)


def test_tree_additions_invalidate_plan(ready_plan, tmp_path):
    directory = tmp_path / "runtime"
    directory.mkdir()
    ready_plan.input_trees[str(directory)] = []
    freeze(ready_plan)
    verify_plan_inputs(ready_plan)
    (directory / "new.py").write_text("new runtime source", encoding="utf-8")
    with pytest.raises(ValueError, match="membership changed"):
        verify_plan_inputs(ready_plan)


def test_exclusive_ledger_lock(tmp_path):
    ledger = tmp_path / "ledger.sqlite"
    with ledger_lock(ledger):
        with pytest.raises(RuntimeError, match="already owned"):
            with ledger_lock(ledger):
                pytest.fail("A second writer acquired the ledger.")


def test_status_does_not_create_nonexistent_ledger(tmp_path):
    ledger = tmp_path / "missing.sqlite"
    with pytest.raises(FileNotFoundError):
        campaign_status(ledger)
    assert not ledger.exists()


def test_resume_preserves_completed_attempts_and_pairs(ready_plan):
    ledger = initialize_ledger(ready_plan)
    first = run_campaign(ledger, max_trials=6, worker=successful_worker)
    assert first["execution_statuses"] == {"completed": 6}
    assert first["studies"]["strictness"]["complete_pairs"] == 4
    assert first["studies"]["strictness"]["gate_and_m1_eligible_pairs"] == 4
    before = ledger_rows(ledger, "attempts")
    worker = Mock(side_effect=AssertionError("Completed trials must not run again."))
    run_campaign(ledger, max_trials=6, retry_failed=True, worker=worker)
    worker.assert_not_called()
    assert ledger_rows(ledger, "attempts") == before
    assert all(Path(row["artifact_dir"]).is_dir() for row in before)


def test_failure_requires_explicit_retry_and_respects_attempt_limit(ready_plan):
    ledger = initialize_ledger(ready_plan)
    failure = Mock(
        return_value=WorkerResult(return_code=7, error="intentional test failure")
    )
    run_campaign(ledger, max_trials=6, worker=failure)
    assert failure.call_count == 6
    run_campaign(ledger, max_trials=6, worker=failure)
    assert failure.call_count == 6
    run_campaign(ledger, max_trials=6, retry_failed=True, worker=failure)
    assert failure.call_count == 12
    result = run_campaign(ledger, max_trials=6, retry_failed=True, worker=failure)
    assert failure.call_count == 12
    assert result["exhausted_trials"] == 6
    assert len(ledger_rows(ledger, "attempts")) == 12


@pytest.mark.parametrize("gate, measured", [(False, True), (True, False)])
def test_failed_scientific_gate_is_not_execution_failure_or_auto_retry(
    ready_plan, gate, measured
):
    ledger = initialize_ledger(ready_plan)
    worker = Mock(return_value=successful_result(gate=gate, measured=measured))
    summary = run_campaign(ledger, max_trials=6, worker=worker)
    assert summary["execution_statuses"] == {"completed": 6}
    assert summary["studies"]["strictness"]["complete_pairs"] == 4
    assert summary["studies"]["strictness"]["gate_and_m1_eligible_pairs"] == 0
    run_campaign(ledger, max_trials=6, retry_failed=True, worker=worker)
    assert worker.call_count == 6


def test_pair_measurement_scope_must_match(ready_plan):
    ledger = initialize_ledger(ready_plan)

    def worker(job, plan, directory, execution_id, stop):
        return successful_result(identity=canonical_hash(job.condition))

    summary = run_campaign(ledger, max_trials=6, worker=worker)
    assert summary["studies"]["strictness"]["complete_pairs"] == 4
    assert summary["studies"]["strictness"]["gate_and_m1_eligible_pairs"] == 0


def test_repository_serialization_and_parallelism(ready_plan):
    ledger = initialize_ledger(ready_plan)
    lock = threading.Lock()
    barrier = threading.Barrier(2)
    active = Counter()
    overlaps = []

    def worker(job, plan, directory, execution_id, stop):
        with lock:
            active[job.repository_key] += 1
            overlaps.append((active[job.repository_key], sum(active.values())))
        barrier.wait(timeout=5)
        time.sleep(0.01)
        with lock:
            active[job.repository_key] -= 1
        return successful_result()

    summary = run_campaign(ledger, max_trials=6, worker=worker)
    assert summary["execution_statuses"] == {"completed": 6}
    assert max(count for count, _ in overlaps) == 1
    assert max(total for _, total in overlaps) == 2


def test_worker_exception_is_recorded_as_failure(ready_plan):
    ledger = initialize_ledger(ready_plan)
    worker = Mock(side_effect=ValueError("Invalid worker report."))
    run_campaign(ledger, max_trials=1, worker=worker)
    attempt = ledger_rows(ledger, "attempts")[0]
    assert attempt["status"] == "failed"
    assert attempt["error"] == "ValueError: Invalid worker report."


def test_uncertain_cleanup_stops_scheduler_until_operator_recovery(ready_plan):
    ready_plan.campaign.execution.max_parallel_trials = 1
    ledger = initialize_ledger(freeze(ready_plan))
    worker = Mock(
        side_effect=WorkerCleanupError("Owned child cleanup could not be confirmed.")
    )
    with pytest.raises(WorkerCleanupError):
        run_campaign(ledger, max_trials=6, worker=worker)
    assert worker.call_count == 1
    assert ledger_rows(ledger, "attempts")[0]["status"] == "running"
    with pytest.raises(RuntimeError, match="explicitly recover"):
        run_campaign(ledger, worker=worker)
    with pytest.raises(ValueError, match="explicit acknowledgement"):
        recover_campaign(ledger, acknowledge_workers_stopped=False)
    recover_campaign(ledger, acknowledge_workers_stopped=True)
    assert ledger_rows(ledger, "attempts")[0]["status"] == "interrupted"


def test_success_without_result_is_not_completed(ready_plan):
    ledger = initialize_ledger(ready_plan)
    summary = run_campaign(
        ledger, max_trials=1, worker=Mock(return_value=WorkerResult(return_code=0))
    )
    assert summary["execution_statuses"]["failed"] == 1
    with pytest.raises(ValidationError, match="comparison provenance"):
        successful_result().result.model_validate(
            {
                "gate_passed": True,
                "m1_available": True,
                "verdict": "acceptable",
                "sampling_control_status": "unsupported",
                "issue_context_sha256": "c" * 64,
            }
        )


def test_exports_include_blocked_incomplete_and_all_attempts(ready_plan, tmp_path):
    ready_plan.jobs[0].blockers = ["Test-only blocker."]
    ledger = initialize_ledger(freeze(ready_plan))
    run_campaign(ledger, max_trials=1, worker=successful_worker)
    output = tmp_path / "export"
    export_campaign(ledger, output)
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    assert summary == campaign_status(ledger)
    with (output / "executions.csv").open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 6
    assert rows[0]["status"] == "blocked"
    assert json.loads(rows[0]["blockers"]) == ["Test-only blocker."]
    assert len(json.loads((output / "attempts.json").read_text(encoding="utf-8"))) == 1
    with (output / "pairs.csv").open(encoding="utf-8", newline="") as stream:
        assert len(list(csv.DictReader(stream))) == 4


def report_for(job, plan, execution_id="test-execution"):
    comparison = compare_structural_metrics(synthetic_input()).model_dump(mode="json")
    return {
        "run": {"execution_id": execution_id},
        "issue": {
            "url": job.issue_url,
            "discussion": {"evidence": ["Test-only frozen issue context."]},
        },
        "subject": {"base_ref": job.base_commit, "repo_path": job.repo_path},
        "run_config": {
            "llm": {"model": plan.campaign.model.alias},
            "swe_runtime": {
                "sha256": canonical_hash(job.runtime.model_dump(mode="json")),
                "task_prompt_sha256": source_hash(job.prompt)
                if job.prompt is not None
                else None,
            },
        },
        "metrics": {
            "design_quality": {"structural": {"status": "ok", "comparison": comparison}}
        },
        "testability_gate": {"build_status": "pass", "test_status": "pass"},
        "mcp": {"judgement": {"overall_verdict": "acceptable"}},
    }


def test_report_validates_identity_runtime_and_measurement_provenance(ready_plan):
    job = ready_plan.jobs[0]
    report = report_for(job, ready_plan)
    result = _validate_report(report, job, ready_plan, "test-execution")
    assert result["delta_struct"] == pytest.approx(0.5)
    assert result["sampling_control_status"] == "unsupported"
    changed = deepcopy(report)
    changed["metrics"]["design_quality"]["structural"]["comparison"]["evidence"][
        "before"
    ][0]["timestamp"] = "2026-02-01T00:00:00Z"
    assert (
        _validate_report(changed, job, ready_plan, "test-execution")[
            "measurement_identity"
        ]
        == result["measurement_identity"]
    )
    changed["metrics"]["design_quality"]["structural"]["comparison"]["evidence"][
        "before"
    ][0]["instrument_version"] = "2"
    assert (
        _validate_report(changed, job, ready_plan, "test-execution")[
            "measurement_identity"
        ]
        != result["measurement_identity"]
    )
    report["run_config"]["swe_runtime"]["sha256"] = "invalid"
    with pytest.raises(ValueError, match="runtime"):
        _validate_report(report, job, ready_plan, "test-execution")


@pytest.mark.parametrize(
    "section, field, value",
    [
        ("run", "execution_id", "wrong"),
        ("issue", "url", "https://github.com/wrong/repo/issues/1"),
        ("subject", "base_ref", "wrong"),
        ("subject", "repo_path", "wrong"),
    ],
)
def test_report_rejects_wrong_trial(ready_plan, section, field, value):
    job = ready_plan.jobs[0]
    report = report_for(job, ready_plan)
    report[section][field] = value
    with pytest.raises(ValueError):
        _validate_report(report, job, ready_plan, "test-execution")


def test_explicit_runtime_loader_missing_file_is_an_error(tmp_path, monkeypatch):
    monkeypatch.setenv("SWE_MCP_CONFIG_PATH", str(tmp_path / "missing.yaml"))
    with pytest.raises(FileNotFoundError):
        SweMcpConfig.load(str(tmp_path))


def test_plan_status_and_export_cli_do_not_invoke_workers(
    ready_plan, tmp_path, monkeypatch, capsys
):
    ledger = initialize_ledger(ready_plan)
    worker = Mock(
        side_effect=AssertionError("Inspection must never execute experiments.")
    )
    monkeypatch.setattr(campaign_runner, "execute_trial", worker)
    monkeypatch.setattr(campaign_runner, "run_campaign", worker)
    assert campaign_runner.main(["status", "--ledger", str(ledger)]) == 0
    assert (
        campaign_runner.main(
            ["export", "--ledger", str(ledger), "--output", str(tmp_path / "export")]
        )
        == 0
    )
    monkeypatch.setattr(
        campaign_runner, "build_campaign_plan", Mock(return_value=ready_plan)
    )
    assert campaign_runner.main(["plan", "--config", "unused.yaml"]) == 0
    worker.assert_not_called()
    assert '"planned_executions": 6' in capsys.readouterr().out


@pytest.fixture
def worker_plan(ready_plan, tmp_path):
    evidence = synthetic_input()
    for stage in ("before", "after"):
        path = tmp_path / f"{stage}.json"
        path.write_text(getattr(evidence, stage)[0].model_dump_json(), encoding="utf-8")
        ready_plan.inputs[str(path)] = file_hash(path)
    configuration = tmp_path / "structural.json"
    configuration.write_text(
        json.dumps(
            {
                "protocol": evidence.protocol.model_dump(mode="json"),
                "analyzers": [
                    {
                        "instrument": "fixture",
                        "kind": "report",
                        "expected_version": "1",
                        "ruleset_id": "synthetic",
                        "ruleset_version": "1",
                        "before_report": "before.json",
                        "after_report": "after.json",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    ready_plan.inputs[str(configuration)] = file_hash(configuration)
    for job in ready_plan.jobs:
        job.structural_config = str(configuration)
        job.prompt = "Human-authored test wording.\r\nKeep the same issue evidence."
    return freeze(ready_plan)


def test_worker_command_and_frozen_runtime_without_launching_process(
    worker_plan, monkeypatch
):
    ledger = initialize_ledger(worker_plan)
    captured = []

    def fake_process(command, **options):
        captured.append((command, options))
        execution_id = command[command.index("--execution-id") + 1]
        report_path = Path(command[command.index("--out-json") + 1])
        report_path.write_text(
            json.dumps(report_for(worker_plan.jobs[0], worker_plan, execution_id)),
            encoding="utf-8",
        )
        return Mock(pid=123456, poll=Mock(return_value=0), returncode=0)

    monkeypatch.setattr(campaign_runner.subprocess, "Popen", fake_process)
    monkeypatch.setenv("SWE_MCP_CONFIG_PATH", "must-not-inherit.yaml")
    monkeypatch.setenv("DEFAULT_MODEL_ENDPOINT", "must-not-inherit")
    summary = run_campaign(ledger, max_trials=1, worker=campaign_runner.execute_trial)
    assert summary["execution_statuses"]["completed"] == 1
    command, options = captured[0]
    assert "--sampling-controls-unavailable" in command
    assert "--temperature" not in command
    assert "--seed" not in command
    assert command[command.index("--head-ref") + 1] == worker_plan.jobs[0].base_commit
    assert "SWE_MCP_CONFIG_PATH" not in options["env"]
    assert "DEFAULT_MODEL_ENDPOINT" not in options["env"]
    runtime = Path(command[command.index("--swe-config") + 1])
    assert yaml.safe_load(runtime.read_text(encoding="utf-8")) == worker_plan.jobs[
        0
    ].runtime.model_dump(mode="json")
    prompt = Path(command[command.index("--task-prompt-file") + 1])
    assert prompt.read_bytes().decode("utf-8") == worker_plan.jobs[0].prompt
    structural = json.loads(
        Path(command[command.index("--structural-analysis-config") + 1]).read_text(
            encoding="utf-8"
        )
    )
    assert Path(structural["analyzers"][0]["before_report"]).parent == runtime.parent
    assert ledger_rows(ledger, "attempts")[0]["pid"] == 123456
    assert json.loads(ledger_rows(ledger, "attempts")[0]["result"])["report_path"]


def test_malformed_worker_report_is_auditable_failure(worker_plan, monkeypatch):
    ledger = initialize_ledger(worker_plan)

    def fake_process(command, **options):
        Path(command[command.index("--out-json") + 1]).write_text(
            "{}", encoding="utf-8"
        )
        return Mock(pid=123456, poll=Mock(return_value=0), returncode=0)

    monkeypatch.setattr(campaign_runner.subprocess, "Popen", fake_process)
    summary = run_campaign(ledger, max_trials=1, worker=campaign_runner.execute_trial)
    assert summary["execution_statuses"]["failed"] == 1
    assert (
        "missing required study provenance"
        in ledger_rows(ledger, "attempts")[0]["error"]
    )


def test_worker_timeout_records_failure_and_cleans_only_owned_process(
    worker_plan, monkeypatch
):
    ledger = initialize_ledger(worker_plan)
    process = Mock(pid=123456, poll=Mock(return_value=None), returncode=None)

    def stop_owned(owned):
        assert owned is process
        process.returncode = -9
        process.poll.return_value = -9

    cleanup = Mock(side_effect=stop_owned)
    monkeypatch.setattr(campaign_runner.subprocess, "Popen", Mock(return_value=process))
    monkeypatch.setattr(campaign_runner, "_kill_owned_tree", cleanup)
    monkeypatch.setattr(
        campaign_runner.time, "monotonic", Mock(side_effect=[0, 100000])
    )
    summary = run_campaign(ledger, max_trials=1, worker=campaign_runner.execute_trial)
    assert summary["execution_statuses"]["failed"] == 1
    assert (
        ledger_rows(ledger, "attempts")[0]["error"] == "Worker exceeded trial timeout."
    )
    cleanup.assert_called_once_with(process)


def test_issue_context_drift_prevents_pair_eligibility(ready_plan):
    ledger = initialize_ledger(ready_plan)

    def worker(job, plan, directory, execution_id, stop):
        result = successful_result()
        result.result.issue_context_sha256 = canonical_hash(job.condition)
        return result

    summary = run_campaign(ledger, max_trials=6, worker=worker)
    assert summary["studies"]["strictness"]["complete_pairs"] == 4
    assert summary["studies"]["strictness"]["gate_and_m1_eligible_pairs"] == 0


def test_explicit_runtime_is_shared_across_subject_roots(
    ready_plan, tmp_path, monkeypatch
):
    runtime = tmp_path / "runtime.yaml"
    runtime.write_text(
        yaml.safe_dump(ready_plan.jobs[0].runtime.model_dump(mode="json")),
        encoding="utf-8",
    )
    monkeypatch.setenv("SWE_MCP_CONFIG_PATH", str(runtime))
    assert SweMcpConfig.load("different-subject-root") == ready_plan.jobs[0].runtime


def test_main_study_cli_forwards_action_and_flags(monkeypatch):
    dispatch = Mock(return_value=0)
    monkeypatch.setattr(main_cli, "run_study_campaign", dispatch)
    monkeypatch.setattr(
        campaign_runner.sys,
        "argv",
        [
            "src.main",
            "study",
            "plan",
            "--config",
            "experiments\\campaign.yaml",
        ],
    )
    main_cli._dispatch()
    dispatch.assert_called_once_with(["plan", "--config", "experiments\\campaign.yaml"])


def test_qualified_strictness_block_is_runnable_but_baseline_pair_is_not(
    configured_plan, worker_plan, tmp_path
):
    repo = tmp_path / "subject"
    subprocess.run(["git", "init", str(repo)], check=True, capture_output=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "-c",
            "user.name=Campaign test",
            "-c",
            "user.email=campaign-test@example.invalid",
            "-c",
            "commit.gpgsign=false",
            "commit",
            "--allow-empty",
            "-m",
            "Test fixture",
        ],
        check=True,
        capture_output=True,
    )
    revision = subprocess.check_output(
        ["git", "-C", str(repo), "rev-parse", "HEAD"], text=True
    ).strip()
    anchor = configured_plan.jobs[0]

    def change(data):
        data["cohorts"]["main"] = {
            "sets": 1,
            "tasks_per_set": 1,
            "bindings": {
                "set01-task01": {
                    "subject_id": anchor.subject_id,
                    "issue_url": anchor.issue_url,
                    "repo_path": str(repo),
                    "base_commit": revision,
                    "structural_config": worker_plan.jobs[0].structural_config,
                    "ai_use_approved": True,
                }
            },
        }

    plan = build_campaign_plan(temporary_manifest(configured_plan, tmp_path, change))
    strict = [job for job in plan.jobs if job.study == "strictness"]
    assert len(strict) == 3
    assert all(not job.blockers for job in strict)
    assert {job.repository_key for job in strict} == {str((repo / ".git").resolve())}
    assert all(job.runtime.verification.language_overrides == {} for job in strict)
    supervised = next(
        job
        for job in plan.jobs
        if job.study == "effectiveness" and job.worker == "mcp_supervised"
    )
    assert supervised.blockers == ["A matched condition in this block is blocked."]
    assert all(job.blockers for job in plan.jobs if job.study == "robustness")
    verify_plan_inputs(plan)


def test_mismatching_task_yaml_cannot_replace_csv_anchors(configured_plan, tmp_path):
    with (WORKSPACE / "data" / "subjects" / "experiment_runs.csv").open(
        newline="", encoding="utf-8-sig"
    ) as stream:
        reader = csv.DictReader(stream)
        fields = reader.fieldnames
        rows = list(reader)
    mismatching = tmp_path / "wrong-task.yaml"
    mismatching.write_text(
        yaml.safe_dump(
            {
                "subject_id": "S999",
                "issue_url": "https://github.com/wrong/repo/issues/1",
            }
        ),
        encoding="utf-8",
    )
    reference = rows[0]["experiment_config"]
    for row in rows:
        if row["experiment_config"] == reference:
            row["experiment_config"] = str(mismatching)
    registry = tmp_path / "runs.csv"
    with registry.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    path = temporary_manifest(
        configured_plan,
        tmp_path,
        lambda data: data.update(planned_runs_registry=str(registry)),
    )
    plan = build_campaign_plan(path)
    job = plan.jobs[0]
    assert job.subject_id == configured_plan.jobs[0].subject_id
    assert job.issue_url == configured_plan.jobs[0].issue_url
    assert any("conflicts with its CSV" in blocker for blocker in job.blockers)


def test_frozen_bytes_support_bom_without_rereading(ready_plan):
    source = Path(next(iter(ready_plan.inputs)))
    content = b"\xef\xbb\xbfregistered input"
    source.write_bytes(content)
    ready_plan.inputs[str(source)] = file_hash(source)
    assert _frozen_bytes(freeze(ready_plan), source) == content


def test_checked_in_strictness_has_90_distinct_execution_yamls(configured_plan):
    directory = WORKSPACE / "experiments" / "strictness"
    with (directory / "executions.csv").open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 90
    assert len(list(directory.glob("*.yaml"))) == 90
    assert len({row["experiment_config"] for row in rows}) == 90
    assert len({row["block"] for row in rows}) == 30
    assert Counter(row["condition"] for row in rows) == {
        "low": 30,
        "medium": 30,
        "high": 30,
    }
    assert sum(bool(row["subject_id"]) for row in rows) == 60
    assert all(row["status"] == "blocked" for row in rows)
    tasks = set()
    for row in rows:
        configuration = directory / row["experiment_config"]
        job = resolve_execution_config(configured_plan, configuration)
        assert job.id == row["run_id"]
        assert configuration.name == campaign_runner._execution_filename(
            configured_plan, job
        )
        assert str(job.runtime.judging.strictness) == row["strictness"]
        payload = yaml.safe_load(configuration.read_text(encoding="utf-8"))
        assert (directory / payload["campaign_config"]).resolve() == Path(
            configured_plan.manifest_path
        )
        if payload["task_config"]:
            task = (directory / payload["task_config"]).resolve()
            assert task.is_file()
            tasks.add(task)
        else:
            assert payload["subject_id"] is None
            assert payload["issue_url"] is None
    assert len(tasks) == 20


def test_materializing_is_deterministic_and_does_not_create_ledger(
    configured_plan, tmp_path
):
    directory = tmp_path / "strictness"
    index = materialize_study(configured_plan, "strictness", directory)
    before = {path.name: path.read_bytes() for path in directory.iterdir()}
    assert materialize_study(configured_plan, "strictness", directory) == index
    assert {path.name: path.read_bytes() for path in directory.iterdir()} == before
    assert len(before) == 91
    assert index.name == "executions.csv"
    assert not list(directory.glob("*.sqlite"))


def test_execution_names_are_readable_and_preserve_required_dimensions(ready_plan):
    job = ready_plan.jobs[0]
    job.subject_id = "S001"
    job.issue_url = "https://github.com/dotnet/runtime/issues/131001"
    job.condition = "low"
    assert (
        campaign_runner._execution_filename(ready_plan, job)
        == "set01-task01-S001-issue131001-low.yaml"
    )
    job.subject_id = None
    job.issue_url = None
    assert (
        campaign_runner._execution_filename(ready_plan, job)
        == "set01-task01-unassigned-low.yaml"
    )
    ready_plan.campaign.studies[0].repetitions = 2
    ready_plan.campaign.studies[0].variants = ["original", "p01"]
    job.repetition = 2
    job.variant = "p01"
    assert (
        campaign_runner._execution_filename(ready_plan, job)
        == "set01-task01-unassigned-r02-p01-low.yaml"
    )
    job.subject_id = "..\\outside"
    with pytest.raises(ValueError, match="Subject ID"):
        campaign_runner._execution_filename(ready_plan, job)


def test_materializing_migrates_only_matching_legacy_filenames(indexed_plan):
    plan, configuration, selected_id = indexed_plan
    job = next(job for job in plan.jobs if job.id == selected_id)
    before = configuration.read_bytes()
    legacy = (
        configuration.parent
        / f"{job.slot}-r{job.repetition:02d}-{job.variant}-{job.condition}.yaml"
    )
    configuration.rename(legacy)
    materialize_study(plan, "strictness", configuration.parent)
    assert not legacy.exists()
    assert configuration.read_bytes() == before
    assert len(list(configuration.parent.glob("*.yaml"))) == 6
    configuration.rename(legacy)
    data = yaml.safe_load(legacy.read_text(encoding="utf-8"))
    data["strictness"] = 0.123
    legacy.write_text(yaml.safe_dump(data), encoding="utf-8")
    with pytest.raises(ValueError, match="safely rename"):
        materialize_study(plan, "strictness", configuration.parent)
    assert legacy.exists()
    assert not configuration.exists()


def test_materializing_rejects_unknown_study_and_unexpected_yamls(
    configured_plan, tmp_path
):
    directory = tmp_path / "strictness"
    with pytest.raises(ValueError, match="no declared executions"):
        materialize_study(configured_plan, "unknown", directory)
    assert not directory.exists()
    directory.mkdir()
    unrelated = directory / "unrelated.yaml"
    unrelated.write_text("untouched", encoding="utf-8")
    with pytest.raises(ValueError, match="unexpected execution YAMLs"):
        materialize_study(configured_plan, "strictness", directory)
    assert unrelated.read_text(encoding="utf-8") == "untouched"
    assert len(list(directory.iterdir())) == 1


@pytest.fixture
def indexed_plan(ready_plan, tmp_path):
    for job in ready_plan.jobs:
        job.proposal_source_runs = []
    freeze(ready_plan)
    directory = tmp_path / "strictness"
    index = materialize_study(ready_plan, "strictness", directory)
    with index.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    return ready_plan, directory / rows[-1]["experiment_config"], rows[-1]["run_id"]


def test_execution_yaml_selects_exactly_one_trial_and_preserves_resume(indexed_plan):
    plan, configuration, selected_id = indexed_plan
    ledger = initialize_ledger(plan)
    worker = Mock(side_effect=successful_worker)
    summary = run_campaign(
        ledger, max_trials=6, execution_config=configuration, worker=worker
    )
    assert worker.call_count == 1
    assert worker.call_args.args[0].id == selected_id
    assert summary["execution_statuses"] == {"completed": 1, "pending": 5}
    run_campaign(ledger, max_trials=6, execution_config=configuration, worker=worker)
    assert worker.call_count == 1
    assert len(ledger_rows(ledger, "attempts")) == 1


@pytest.mark.parametrize(
    "field,value",
    [
        ("job_id", "not-a-trial"),
        ("condition", "different"),
        ("strictness", 0.123),
        ("runtime_sha256", "0" * 64),
        ("task_config", "different-task.yaml"),
        ("campaign_config", "different-campaign.yaml"),
        ("blockers", ["fabricated blocker"]),
    ],
)
def test_execution_yaml_cannot_override_frozen_trial(indexed_plan, field, value):
    plan, configuration, _ = indexed_plan
    ledger = initialize_ledger(plan)
    data = yaml.safe_load(configuration.read_text(encoding="utf-8"))
    data[field] = value
    configuration.write_text(yaml.safe_dump(data), encoding="utf-8")
    worker = Mock(
        side_effect=AssertionError("Invalid execution YAML must not invoke a worker.")
    )
    with pytest.raises(ValueError, match="Execution configuration"):
        run_campaign(ledger, execution_config=configuration, worker=worker)
    worker.assert_not_called()
    assert ledger_rows(ledger, "attempts") == []


def test_blocked_execution_yaml_cannot_bypass_prerequisites(configured_plan, tmp_path):
    directory = tmp_path / "strictness"
    index = materialize_study(configured_plan, "strictness", directory)
    with index.open(encoding="utf-8", newline="") as stream:
        configuration = directory / next(csv.DictReader(stream))["experiment_config"]
    ledger = initialize_ledger(configured_plan, tmp_path / "blocked.sqlite")
    worker = Mock(
        side_effect=AssertionError("Blocked selection must not invoke a worker.")
    )
    with pytest.raises(ValueError, match="Selected execution is blocked"):
        run_campaign(ledger, execution_config=configuration, worker=worker)
    worker.assert_not_called()
    assert ledger_rows(ledger, "attempts") == []


def test_materialize_cli_never_initializes_ledger_or_executes_workers(
    configured_plan, tmp_path, monkeypatch, capsys
):
    initialize = Mock(
        side_effect=AssertionError("Materialize must not create a ledger.")
    )
    worker = Mock(side_effect=AssertionError("Materialize must not execute a trial."))
    monkeypatch.setattr(
        campaign_runner, "build_campaign_plan", Mock(return_value=configured_plan)
    )
    monkeypatch.setattr(campaign_runner, "initialize_ledger", initialize)
    monkeypatch.setattr(campaign_runner, "run_campaign", worker)
    assert (
        campaign_runner.main(
            [
                "materialize",
                "--config",
                "unused.yaml",
                "--study",
                "strictness",
                "--output",
                str(tmp_path / "strictness"),
            ]
        )
        == 0
    )
    initialize.assert_not_called()
    worker.assert_not_called()
    assert "Materialized 90 execution YAMLs" in capsys.readouterr().out
