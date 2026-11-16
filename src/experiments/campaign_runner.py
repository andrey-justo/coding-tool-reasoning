from __future__ import annotations

import argparse
import csv
import hashlib
import importlib
import io
import json
import logging
import os
import re
import signal
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
from collections import Counter
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from contextlib import closing, contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterator

import yaml
from pydantic import model_validator

from src.evaluation.metrics.structural import canonical_hash, source_hash
from src.evaluation.structural_analysis import StructuralAnalysisConfig
from src.experiments.campaign_plan import (
    WORKSPACE,
    CampaignJob,
    CampaignPlan,
    build_campaign_plan,
    verify_plan_inputs,
)
from src.models.structural_metrics import StructuralComparison
from src.models.study_campaign import StudyExecutionConfig, StudyModel

logger = logging.getLogger(__name__)


class TrialResult(StudyModel):
    gate_passed: bool
    m1_available: bool
    delta_struct: float | None = None
    protocol_sha256: str | None = None
    measurement_identity: str | None = None
    issue_context_sha256: str
    verdict: str
    sampling_control_status: str
    report_path: str | None = None

    @model_validator(mode="after")
    def metric_provenance(self) -> TrialResult:
        if self.m1_available and (
            self.delta_struct is None
            or not self.protocol_sha256
            or not self.measurement_identity
        ):
            raise ValueError(
                "Available M-1 measurements require their delta and comparison provenance."
            )
        return self


class WorkerResult(StudyModel):
    return_code: int
    result: TrialResult | None = None
    error: str | None = None
    interrupted: bool = False


class WorkerCleanupError(RuntimeError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def ledger_lock(path: Path) -> Iterator[None]:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.with_suffix(path.suffix + ".lock").open("a+b") as stream:
        if stream.tell() == 0:
            stream.write(b"\0")
            stream.flush()
        stream.seek(0)
        locking = importlib.import_module("msvcrt" if os.name == "nt" else "fcntl")
        try:
            if os.name == "nt":
                locking.locking(stream.fileno(), locking.LK_NBLCK, 1)
            else:
                locking.flock(stream.fileno(), locking.LOCK_EX | locking.LOCK_NB)
        except OSError as error:
            raise RuntimeError(
                "The campaign ledger is already owned by another operation."
            ) from error
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == "nt":
                locking.locking(stream.fileno(), locking.LK_UNLCK, 1)
            else:
                locking.flock(stream.fileno(), locking.LOCK_UN)


def _connect(path: Path, *, create: bool = False) -> sqlite3.Connection:
    if not create and not path.is_file():
        raise FileNotFoundError(f"Study ledger does not exist: {path}")
    connection = sqlite3.connect(path, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    return connection


def initialize_ledger(plan: CampaignPlan, ledger: Path | None = None) -> Path:
    verify_plan_inputs(plan)
    path = (ledger or Path(plan.ledger_path)).resolve()
    if str(path) != plan.ledger_path:
        plan = plan.model_copy(deep=True)
        plan.ledger_path = str(path)
        plan.plan_sha256 = canonical_hash(
            plan.model_dump(mode="json", exclude={"plan_sha256"})
        )
    with ledger_lock(path), closing(
        _connect(path, create=True)
    ) as connection, connection:
        connection.executescript("""
            CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY, position INTEGER NOT NULL UNIQUE,
                status TEXT NOT NULL CHECK(status IN ('pending','blocked','running','completed','failed','interrupted')),
                spec TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0, result TEXT
            );
            CREATE TABLE IF NOT EXISTS attempts (
                job_id TEXT NOT NULL REFERENCES jobs(id), number INTEGER NOT NULL,
                execution_id TEXT NOT NULL UNIQUE, status TEXT NOT NULL,
                started_at TEXT NOT NULL, finished_at TEXT, pid INTEGER,
                artifact_dir TEXT NOT NULL, return_code INTEGER, error TEXT, result TEXT,
                PRIMARY KEY(job_id, number)
            );
            CREATE TABLE IF NOT EXISTS pairs (id TEXT PRIMARY KEY, spec TEXT NOT NULL);
        """)
        existing = connection.execute(
            "SELECT value FROM metadata WHERE key='plan'"
        ).fetchone()
        if existing:
            frozen = CampaignPlan.model_validate_json(existing["value"])
            if frozen.plan_sha256 != plan.plan_sha256:
                raise ValueError(
                    "This ledger belongs to a different frozen plan; use a new ledger/artifact root."
                )
            return path
        connection.execute(
            "INSERT INTO metadata VALUES ('plan', ?)", (plan.model_dump_json(),)
        )
        connection.executemany(
            "INSERT INTO jobs(id,position,status,spec) VALUES (?,?,?,?)",
            [
                (
                    job.id,
                    position,
                    "blocked" if job.blockers else "pending",
                    job.model_dump_json(),
                )
                for position, job in enumerate(plan.jobs)
            ],
        )
        connection.executemany(
            "INSERT INTO pairs VALUES (?,?)",
            [(pair.id, pair.model_dump_json()) for pair in plan.pairs],
        )
    return path


def load_plan(connection: sqlite3.Connection) -> CampaignPlan:
    row = connection.execute("SELECT value FROM metadata WHERE key='plan'").fetchone()
    if row is None:
        raise ValueError("The ledger has no initialized study plan.")
    return CampaignPlan.model_validate_json(row["value"])


def _frozen_bytes(plan: CampaignPlan, path: Path) -> bytes:
    content = path.read_bytes()
    if hashlib.sha256(content).hexdigest() != plan.inputs.get(str(path.resolve())):
        raise ValueError(f"Frozen input changed before worker launch: {path}")
    return content


def _kill_owned_tree(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    try:
        if os.name == "nt":
            stopped = subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                capture_output=True,
                check=False,
                timeout=30,
            )
            if stopped.returncode and process.poll() is None:
                raise WorkerCleanupError(
                    f"Could not stop owned worker process tree PID {process.pid}."
                )
        else:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                if process.poll() is None:
                    raise WorkerCleanupError(
                        f"Could not locate owned worker process group PID {process.pid}."
                    )
        process.wait(timeout=30)
    except (OSError, subprocess.SubprocessError) as error:
        raise WorkerCleanupError(
            f"Could not confirm cleanup of owned worker PID {process.pid}: {error}"
        ) from error


def _validate_report(
    report: dict, job: CampaignJob, plan: CampaignPlan, execution_id: str
) -> dict:
    if (
        report["run"]["execution_id"] != execution_id
        or report["issue"]["url"] != job.issue_url
    ):
        raise ValueError(
            "Worker report execution/issue does not match the scheduled trial."
        )
    if report["subject"]["base_ref"] != job.base_commit:
        raise ValueError("Worker report used a different baseline revision.")
    if Path(report["subject"]["repo_path"]).resolve() != Path(job.repo_path).resolve():
        raise ValueError("Worker report used a different repository.")
    if report["run_config"]["llm"]["model"] != plan.campaign.model.alias:
        raise ValueError("Worker report used a different model.")
    runtime = report["run_config"]["swe_runtime"]
    if runtime["sha256"] != canonical_hash(job.runtime.model_dump(mode="json")):
        raise ValueError("Worker did not use the frozen runtime configuration.")
    expected_prompt = source_hash(job.prompt) if job.prompt is not None else None
    if runtime["task_prompt_sha256"] != expected_prompt:
        raise ValueError("Worker report used different task wording.")
    design = report["metrics"]["design_quality"]["structural"]
    gate = report["testability_gate"]
    measured = design["status"] == "ok"
    comparison = (
        StructuralComparison.model_validate(design["comparison"]) if measured else None
    )
    return {
        "gate_passed": gate["build_status"] == "pass" and gate["test_status"] == "pass",
        "m1_available": measured,
        "delta_struct": comparison.delta_struct if measured else None,
        "protocol_sha256": comparison.protocol_sha256 if measured else None,
        "verdict": report["mcp"]["judgement"]["overall_verdict"],
        "sampling_control_status": "unsupported"
        if plan.campaign.model.provider == "CopilotSDK"
        else "requested-not-independently-verified",
        "issue_context_sha256": canonical_hash(report["issue"]["discussion"]),
        "measurement_identity": canonical_hash(
            {
                "baseline": comparison.before.model_dump(mode="json"),
                "instruments": [
                    {
                        **item.model_dump(
                            mode="json",
                            exclude={
                                "timestamp",
                                "source",
                                "counts",
                                "files",
                                "analyzed_rules",
                            },
                        ),
                        "files": [
                            file.model_dump(mode="json")
                            for file in sorted(item.files, key=lambda file: file.path)
                        ],
                        "analyzed_rules": sorted(item.analyzed_rules),
                        "counts": [
                            count.model_dump(mode="json")
                            for count in sorted(
                                item.counts,
                                key=lambda count: (count.rule_id, count.path),
                            )
                        ],
                    }
                    for item in sorted(
                        comparison.evidence.before, key=lambda item: item.instrument
                    )
                ],
            }
        )
        if measured
        else None,
    }


def execute_trial(
    job: CampaignJob,
    plan: CampaignPlan,
    artifact_dir: Path,
    execution_id: str,
    stop: threading.Event,
) -> WorkerResult:
    if job.worker != "mcp_supervised" or job.blockers:
        raise ValueError("Cannot execute an unsupported or blocked condition.")
    verify_plan_inputs(plan)
    artifact_dir.mkdir(parents=True, exist_ok=False)
    runtime_path = artifact_dir / "swe_mcp_config.yaml"
    runtime_path.write_text(
        yaml.safe_dump(job.runtime.model_dump(mode="json")), encoding="utf-8"
    )
    structural_path = Path(job.structural_config)
    structural = StructuralAnalysisConfig.model_validate_json(
        _frozen_bytes(plan, structural_path)
    )
    for analyzer in structural.analyzers:
        if analyzer.enabled and analyzer.kind == "report":
            for stage in ("before_report", "after_report"):
                original = Path(getattr(analyzer, stage).replace("\\", "/"))
                original = (structural_path.parent / original).resolve()
                copied = (
                    artifact_dir
                    / f"{canonical_hash(analyzer.instrument)[:12]}-{stage}.json"
                )
                copied.write_bytes(_frozen_bytes(plan, original))
                setattr(analyzer, stage, str(copied))
    structural_copy = artifact_dir / "structural.json"
    structural_copy.write_text(structural.model_dump_json(), encoding="utf-8")
    command = [
        sys.executable,
        "-m",
        "src.experiments.issue_mcp_experiment",
        "--issue-url",
        job.issue_url,
        "--repo-path",
        job.repo_path,
        "--base-ref",
        job.base_commit,
        "--head-ref",
        job.base_commit,
        "--model",
        plan.campaign.model.alias,
        "--swe-config",
        str(runtime_path),
        "--structural-analysis-config",
        str(structural_copy),
        "--execution-id",
        execution_id,
        "--verification-timeout-seconds",
        str(plan.campaign.execution.verification_timeout_seconds),
    ]
    for flag, name in (
        ("--out-json", "report.json"),
        ("--out-md", "report.md"),
        ("--out-csv", "metrics.csv"),
        ("--out-log", "execution.log"),
    ):
        command.extend((flag, str(artifact_dir / name)))
    if job.prompt is not None:
        prompt = artifact_dir / "task.txt"
        prompt.write_text(job.prompt, encoding="utf-8", newline="")
        command.extend(("--task-prompt-file", str(prompt)))
    if job.issue_context_cutoff:
        command.extend(("--issue-context-cutoff", job.issue_context_cutoff))
    if plan.campaign.model.provider == "CopilotSDK":
        command.append("--sampling-controls-unavailable")
    else:
        for flag, value in (
            ("--temperature", plan.campaign.model.temperature),
            ("--seed", plan.campaign.model.seed),
        ):
            if value is not None:
                command.extend((flag, str(value)))
    environment = os.environ.copy()
    environment.pop("SWE_MCP_CONFIG_PATH", None)
    environment.pop("DEFAULT_MODEL_ENDPOINT", None)
    environment["PYTHONIOENCODING"] = "utf-8"
    started = time.monotonic()
    with (artifact_dir / "stdout.log").open("w", encoding="utf-8") as stdout, (
        artifact_dir / "stderr.log"
    ).open("w", encoding="utf-8") as stderr:
        process = subprocess.Popen(
            command,
            cwd=WORKSPACE,
            env=environment,
            stdout=stdout,
            stderr=stderr,
            start_new_session=os.name != "nt",
        )
        try:
            with closing(_connect(Path(plan.ledger_path))) as connection, connection:
                updated = connection.execute(
                    "UPDATE attempts SET pid=? WHERE execution_id=?",
                    (process.pid, execution_id),
                )
                if updated.rowcount != 1:
                    raise ValueError("Worker has no matching reserved ledger attempt.")
            while process.poll() is None:
                if (
                    stop.is_set()
                    or time.monotonic() - started
                    > plan.campaign.execution.trial_timeout_seconds
                ):
                    _kill_owned_tree(process)
                    return WorkerResult(
                        return_code=process.returncode,
                        interrupted=stop.is_set(),
                        error="Worker interrupted."
                        if stop.is_set()
                        else "Worker exceeded trial timeout.",
                    )
                stop.wait(0.2)
            code = process.returncode
        finally:
            if process.poll() is None:
                _kill_owned_tree(process)
    if code != 0:
        return WorkerResult(
            return_code=code, error=f"Worker exited with code {code}; see stderr.log."
        )
    report_path = artifact_dir / "report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    try:
        result = _validate_report(report, job, plan, execution_id)
    except (KeyError, TypeError) as error:
        raise ValueError(
            "Worker report is missing required study provenance or metric fields."
        ) from error
    result["report_path"] = str(report_path)
    return WorkerResult(return_code=0, result=result)


Worker = Callable[[CampaignJob, CampaignPlan, Path, str, threading.Event], WorkerResult]


def run_campaign(
    ledger: Path,
    *,
    max_trials: int = 1,
    retry_failed: bool = False,
    execution_config: Path | None = None,
    worker: Worker = execute_trial,
) -> dict:
    if max_trials < 1:
        raise ValueError("max_trials must be positive.")
    with ledger_lock(ledger), closing(_connect(ledger)) as connection:
        plan = load_plan(connection)
        verify_plan_inputs(plan)
        selected_job = (
            resolve_execution_config(plan, execution_config)
            if execution_config
            else None
        )
        if selected_job and selected_job.blockers:
            raise ValueError(
                f"Selected execution is blocked: {'; '.join(selected_job.blockers)}"
            )
        if connection.execute(
            "SELECT 1 FROM jobs WHERE status='running' LIMIT 1"
        ).fetchone():
            raise RuntimeError(
                "Interrupted scheduler detected. Stop/inspect its workers, then explicitly recover the ledger."
            )
        statuses = (
            ("pending", "failed", "interrupted") if retry_failed else ("pending",)
        )
        candidates = [
            row
            for row in connection.execute("SELECT * FROM jobs ORDER BY position")
            if row["status"] in statuses
            and row["attempts"] < plan.campaign.execution.max_attempts_per_trial
            and (selected_job is None or row["id"] == selected_job.id)
        ]
        stop = threading.Event()
        active = {}
        repositories = set()
        started = 0

        def finish(future) -> None:
            row, directory = active.pop(future)
            job = CampaignJob.model_validate_json(row["spec"])
            repositories.remove(os.path.normcase(job.repository_key or job.repo_path))
            try:
                outcome = future.result()
            except WorkerCleanupError as error:
                stop.set()
                with connection:
                    connection.execute(
                        "UPDATE attempts SET error=? WHERE job_id=? AND number=?",
                        (str(error), job.id, row["attempts"] + 1),
                    )
                raise
            except (
                OSError,
                ValueError,
                RuntimeError,
                subprocess.SubprocessError,
            ) as error:
                logger.exception("Campaign worker failed for %s", job.id)
                outcome = WorkerResult(
                    return_code=-1, error=f"{type(error).__name__}: {error}"
                )
            if outcome.return_code == 0 and outcome.result is None:
                outcome.error = (
                    "Worker exited successfully without a validated trial result."
                )
            status = (
                "interrupted"
                if outcome.interrupted
                else (
                    "completed"
                    if outcome.return_code == 0 and outcome.result is not None
                    else "failed"
                )
            )
            result = (
                outcome.result.model_dump_json() if outcome.result is not None else None
            )
            with connection:
                connection.execute(
                    "UPDATE attempts SET status=?,finished_at=?,return_code=?,error=?,result=? WHERE job_id=? AND number=?",
                    (
                        status,
                        _now(),
                        outcome.return_code,
                        outcome.error,
                        result,
                        job.id,
                        row["attempts"] + 1,
                    ),
                )
                connection.execute(
                    "UPDATE jobs SET status=?,result=? WHERE id=?",
                    (status, result, job.id),
                )

        with ThreadPoolExecutor(
            max_workers=plan.campaign.execution.max_parallel_trials
        ) as pool:
            try:
                while active or (candidates and started < max_trials):
                    while (
                        started < max_trials
                        and len(active) < plan.campaign.execution.max_parallel_trials
                    ):
                        selected = next(
                            (
                                row
                                for row in candidates
                                if os.path.normcase(
                                    CampaignJob.model_validate_json(
                                        row["spec"]
                                    ).repository_key
                                    or CampaignJob.model_validate_json(
                                        row["spec"]
                                    ).repo_path
                                )
                                not in repositories
                            ),
                            None,
                        )
                        if selected is None:
                            break
                        candidates.remove(selected)
                        job = CampaignJob.model_validate_json(selected["spec"])
                        attempt = selected["attempts"] + 1
                        identity = canonical_hash([plan.plan_sha256, job.id])[:20]
                        execution_id = f"{identity}-a{attempt:03d}"
                        directory = (
                            Path(plan.artifact_root)
                            / "trials"
                            / identity
                            / f"attempt-{attempt:03d}"
                        )
                        with connection:
                            connection.execute(
                                "UPDATE jobs SET status='running',attempts=? WHERE id=?",
                                (attempt, job.id),
                            )
                            connection.execute(
                                "INSERT INTO attempts(job_id,number,execution_id,status,started_at,artifact_dir) VALUES (?,?,?,'running',?,?)",
                                (job.id, attempt, execution_id, _now(), str(directory)),
                            )
                        repositories.add(
                            os.path.normcase(job.repository_key or job.repo_path)
                        )
                        active[
                            pool.submit(
                                worker, job, plan, directory, execution_id, stop
                            )
                        ] = (selected, directory)
                        started += 1
                    if active:
                        done, _ = wait(active, return_when=FIRST_COMPLETED)
                        for future in done:
                            finish(future)
            except (KeyboardInterrupt, WorkerCleanupError):
                stop.set()
                for future in list(active):
                    finish(future)
                raise
            finally:
                stop.set()
    summary = campaign_status(ledger)
    summary["last_dispatch"] = {
        "started": started,
        "status": "executed" if started else "no-eligible-trials",
    }
    return summary


def recover_campaign(ledger: Path, *, acknowledge_workers_stopped: bool) -> None:
    if not acknowledge_workers_stopped:
        raise ValueError(
            "Recovery requires explicit acknowledgement that all previous workers have stopped."
        )
    with ledger_lock(ledger), closing(_connect(ledger)) as connection, connection:
        load_plan(connection)
        connection.execute(
            "UPDATE attempts SET status='interrupted',finished_at=?,error=? WHERE status='running'",
            (
                _now(),
                "Operator acknowledged stopped workers after scheduler interruption.",
            ),
        )
        connection.execute(
            "UPDATE jobs SET status='interrupted' WHERE status='running'"
        )


def campaign_status(ledger: Path) -> dict:
    with closing(_connect(ledger)) as connection:
        plan = load_plan(connection)
        rows = list(connection.execute("SELECT id,status,result,attempts FROM jobs"))
    return _summarize(plan, rows)


def _summarize(plan: CampaignPlan, rows: list) -> dict:
    by_id = {row["id"]: row for row in rows}
    studies = {}
    for study in plan.campaign.studies:
        jobs = [job for job in plan.jobs if job.study == study.id]
        pairs = [pair for pair in plan.pairs if pair.study == study.id]
        complete = []
        eligible = []
        for pair in pairs:
            records = [by_id[pair.control_job], by_id[pair.treatment_job]]
            if all(row["status"] == "completed" for row in records):
                complete.append(pair.id)
                results = [json.loads(row["result"]) for row in records]
                if (
                    all(
                        result["gate_passed"] and result["m1_available"]
                        for result in results
                    )
                    and len({result["protocol_sha256"] for result in results}) == 1
                    and len({result["measurement_identity"] for result in results}) == 1
                    and len({result["issue_context_sha256"] for result in results}) == 1
                ):
                    eligible.append(pair.id)
        studies[study.id] = {
            "planned_executions": len(jobs),
            "execution_statuses": dict(
                Counter(by_id[job.id]["status"] for job in jobs)
            ),
            "declared_blocks": len({(job.cohort, job.slot) for job in jobs}),
            "assigned_tasks": len(
                {
                    (job.subject_id, job.issue_url)
                    for job in jobs
                    if job.subject_id and job.issue_url
                }
            ),
            "unique_subjects": len({job.subject_id for job in jobs if job.subject_id}),
            "comparisons": dict(Counter(pair.comparison for pair in pairs)),
            "complete_pairs": len(complete),
            "incomplete_pairs": len(pairs) - len(complete),
            "gate_and_m1_eligible_pairs": len(eligible),
        }
    return {
        "campaign_id": plan.campaign.campaign_id,
        "mode": plan.campaign.mode,
        "plan_sha256": plan.plan_sha256,
        "sampling_controls": "unsupported"
        if plan.campaign.model.provider == "CopilotSDK"
        else "requested-not-independently-verified",
        "planned_executions": len(plan.jobs),
        "planned_pair_records": len(plan.pairs),
        "execution_statuses": dict(Counter(row["status"] for row in rows)),
        "blocker_counts": dict(
            Counter(reason for job in plan.jobs for reason in job.blockers)
        ),
        "registry_rows": len(plan.registry_audit),
        "malformed_registry_rows": sum(
            bool(row["errors"]) for row in plan.registry_audit
        ),
        "exhausted_trials": sum(
            row["status"] in {"failed", "interrupted"}
            and row["attempts"] >= plan.campaign.execution.max_attempts_per_trial
            for row in rows
        ),
        "studies": studies,
    }


def _atomic_write(path: Path, content: str) -> None:
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", newline="", dir=path.parent, delete=False
    ) as stream:
        temporary = Path(stream.name)
        stream.write(content)
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _execution_definition(
    plan: CampaignPlan, job: CampaignJob, directory: Path
) -> StudyExecutionConfig:
    task_config = None
    if job.proposal_source_runs and plan.campaign.planned_runs_registry:
        root = (
            Path(plan.manifest_path).parent
            / plan.campaign.config_root.replace("\\", "/")
        ).resolve()
        registry = (
            root / plan.campaign.planned_runs_registry.replace("\\", "/")
        ).resolve()
        with io.StringIO(_frozen_bytes(plan, registry).decode("utf-8-sig")) as stream:
            references = {
                row["experiment_config"]
                for row in csv.DictReader(stream)
                if row["run_id"] in job.proposal_source_runs
            }
        if len(references) != 1:
            raise ValueError(f"Trial {job.id} has no unique shared task configuration.")
        task = (root / next(iter(references)).replace("\\", "/")).resolve()
        task_config = os.path.relpath(task, directory)
    return StudyExecutionConfig(
        campaign_config=os.path.relpath(plan.manifest_path, directory),
        task_config=task_config,
        job_id=job.id,
        study=job.study,
        cohort=job.cohort,
        slot=job.slot,
        repetition=job.repetition,
        variant=job.variant,
        block_key=job.block_key,
        subject_id=job.subject_id,
        issue_url=job.issue_url,
        condition=job.condition,
        worker=job.worker,
        strictness=job.runtime.judging.strictness,
        runtime_sha256=canonical_hash(job.runtime.model_dump(mode="json")),
        status="blocked" if job.blockers else "planned",
        blockers=job.blockers,
    )


def _execution_filename(plan: CampaignPlan, job: CampaignJob) -> str:
    study = next(study for study in plan.campaign.studies if study.id == job.study)
    subject = job.subject_id or "unassigned"
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]*", subject):
        raise ValueError(
            f"Subject ID cannot be used in an execution filename: {subject}"
        )
    issue = re.fullmatch(
        r"https://github\.com/[^/]+/[^/]+/issues/([1-9][0-9]*)/?", job.issue_url or ""
    )
    parts = [job.slot, subject]
    if issue:
        parts.append(f"issue{issue[1]}")
    elif job.subject_id:
        parts.append("unassigned")
    if study.repetitions > 1:
        parts.append(f"r{job.repetition:02d}")
    if len(study.variants) > 1 or job.variant != "original":
        parts.append(job.variant)
    parts.append(job.condition)
    return "-".join(parts) + ".yaml"


def materialize_study(plan: CampaignPlan, study: str, output: Path) -> Path:
    verify_plan_inputs(plan)
    jobs = [job for job in plan.jobs if job.study == study]
    if not jobs:
        raise ValueError(f"Study has no declared executions: {study}")
    output = output.resolve()
    definitions = {
        _execution_filename(plan, job): _execution_definition(plan, job, output)
        for job in jobs
    }
    if len(definitions) != len(jobs):
        raise ValueError("Study executions do not have unique configuration filenames.")
    unexpected = {path.name for path in output.glob("*.yaml")} - set(definitions)
    legacy = {
        f"{job.slot}-r{job.repetition:02d}-{job.variant}-{job.condition}.yaml": _execution_filename(
            plan, job
        )
        for job in jobs
    }
    migrations = {}
    for filename in sorted(unexpected & legacy.keys()):
        destination = legacy[filename]
        existing = StudyExecutionConfig.model_validate(
            yaml.safe_load((output / filename).read_text(encoding="utf-8"))
        )
        if existing != definitions[destination] or (output / destination).exists():
            raise ValueError(
                f"Cannot safely rename existing execution configuration: {filename}"
            )
        migrations[filename] = destination
    unexpected -= migrations.keys()
    if unexpected:
        raise ValueError(
            f"Output contains unexpected execution YAMLs; use a new directory: {sorted(unexpected)}"
        )
    output.mkdir(parents=True, exist_ok=True)
    for filename, destination in migrations.items():
        (output / filename).rename(output / destination)
    with io.StringIO(newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=[
                "run_id",
                "rq",
                "study",
                "block",
                "subject_id",
                "issue_url",
                "condition",
                "strictness",
                "status",
                "experiment_config",
            ],
        )
        writer.writeheader()
        for job, (filename, definition) in zip(jobs, definitions.items(), strict=True):
            _atomic_write(
                output / filename,
                yaml.safe_dump(definition.model_dump(mode="json"), sort_keys=False),
            )
            writer.writerow(
                {
                    "run_id": job.id,
                    "rq": job.rq,
                    "study": job.study,
                    "block": job.block_key,
                    "subject_id": job.subject_id,
                    "issue_url": job.issue_url,
                    "condition": job.condition,
                    "strictness": definition.strictness,
                    "status": definition.status,
                    "experiment_config": filename,
                }
            )
        registry = output / "executions.csv"
        _atomic_write(registry, stream.getvalue())
    return registry


def resolve_execution_config(plan: CampaignPlan, configuration: Path) -> CampaignJob:
    configuration = configuration.resolve()
    definition = StudyExecutionConfig.model_validate(
        yaml.safe_load(configuration.read_text(encoding="utf-8"))
    )
    matches = [job for job in plan.jobs if job.id == definition.job_id]
    if len(matches) != 1:
        raise ValueError(
            "Execution configuration does not identify a trial in this frozen plan."
        )
    job = matches[0]
    if definition != _execution_definition(plan, job, configuration.parent):
        raise ValueError(
            "Execution configuration no longer matches the frozen trial; regenerate it from the qualified campaign."
        )
    return job


def export_campaign(ledger: Path, output: Path) -> None:
    with closing(_connect(ledger)) as connection:
        connection.execute("BEGIN")
        plan = load_plan(connection)
        rows = {
            row["id"]: dict(row) for row in connection.execute("SELECT * FROM jobs")
        }
        attempts = [
            dict(row)
            for row in connection.execute(
                "SELECT * FROM attempts ORDER BY job_id,number"
            )
        ]
    output.mkdir(parents=True, exist_ok=True)
    _atomic_write(output / "plan.json", plan.model_dump_json(indent=2))
    _atomic_write(
        output / "summary.json",
        json.dumps(_summarize(plan, list(rows.values())), indent=2),
    )
    _atomic_write(output / "attempts.json", json.dumps(attempts, indent=2))
    with io.StringIO(newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=[
                "job_id",
                "study",
                "block",
                "subject_id",
                "issue_url",
                "set",
                "repetition",
                "variant",
                "condition",
                "status",
                "attempts",
                "blockers",
            ],
        )
        writer.writeheader()
        for job in plan.jobs:
            writer.writerow(
                {
                    "job_id": job.id,
                    "study": job.study,
                    "block": job.block_key,
                    "subject_id": job.subject_id,
                    "issue_url": job.issue_url,
                    "set": job.set_index,
                    "repetition": job.repetition,
                    "variant": job.variant,
                    "condition": job.condition,
                    "status": rows[job.id]["status"],
                    "attempts": rows[job.id]["attempts"],
                    "blockers": json.dumps(job.blockers),
                }
            )
        _atomic_write(output / "executions.csv", stream.getvalue())
    with io.StringIO(newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=[
                "pair_id",
                "study",
                "comparison",
                "block",
                "control_job",
                "treatment_job",
            ],
        )
        writer.writeheader()
        writer.writerows(
            {
                "pair_id": pair.id,
                "study": pair.study,
                "comparison": pair.comparison,
                "block": pair.block_key,
                "control_job": pair.control_job,
                "treatment_job": pair.treatment_job,
            }
            for pair in plan.pairs
        )
        _atomic_write(output / "pairs.csv", stream.getvalue())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Configure, inspect and resume paired study campaigns."
    )
    commands = parser.add_subparsers(dest="action", required=True)
    planning = commands.add_parser(
        "plan", help="Validate and persist a plan without launching experiments."
    )
    planning.add_argument("--config", type=Path, required=True)
    planning.add_argument("--ledger", type=Path)
    planning.add_argument("--export", type=Path)
    materializing = commands.add_parser(
        "materialize",
        help="Write one YAML per study execution and a CSV index, without running experiments.",
    )
    materializing.add_argument("--config", type=Path, required=True)
    materializing.add_argument("--study", required=True)
    materializing.add_argument("--output", type=Path, required=True)
    running = commands.add_parser(
        "run", help="Explicitly execute eligible trials from an initialized ledger."
    )
    running.add_argument("--ledger", type=Path, required=True)
    running.add_argument("--max-trials", type=int, default=1)
    running.add_argument("--retry-failed", action="store_true")
    running.add_argument(
        "--execution-config",
        type=Path,
        help="Select only the trial described by a materialized execution YAML.",
    )
    status = commands.add_parser("status")
    status.add_argument("--ledger", type=Path, required=True)
    exporting = commands.add_parser("export")
    exporting.add_argument("--ledger", type=Path, required=True)
    exporting.add_argument("--output", type=Path, required=True)
    recovery = commands.add_parser("recover")
    recovery.add_argument("--ledger", type=Path, required=True)
    recovery.add_argument("--acknowledge-workers-stopped", action="store_true")
    args = parser.parse_args(argv)
    if args.action == "materialize":
        plan = build_campaign_plan(args.config)
        registry = materialize_study(plan, args.study, args.output)
        print(
            f"Materialized {sum(job.study == args.study for job in plan.jobs)} execution YAMLs; CSV index: {registry}"
        )
        return 0
    summary = None
    if args.action == "plan":
        plan = build_campaign_plan(args.config)
        ledger = initialize_ledger(plan, args.ledger)
        if args.export:
            export_campaign(ledger, args.export)
    else:
        ledger = args.ledger.resolve()
        if not ledger.is_file():
            raise FileNotFoundError(f"Study ledger does not exist: {ledger}")
        if args.action == "run":
            summary = run_campaign(
                ledger,
                max_trials=args.max_trials,
                retry_failed=args.retry_failed,
                execution_config=args.execution_config,
            )
        elif args.action == "recover":
            recover_campaign(
                ledger, acknowledge_workers_stopped=args.acknowledge_workers_stopped
            )
        elif args.action == "export":
            export_campaign(ledger, args.output)
    summary = summary if summary is not None else campaign_status(ledger)
    print(json.dumps(summary, indent=2))
    if args.action == "run":
        if summary["execution_statuses"].get("failed") or summary[
            "execution_statuses"
        ].get("interrupted"):
            return 1
        if (
            summary["last_dispatch"]["started"] == 0
            and summary["execution_statuses"].get("blocked")
            == summary["planned_executions"]
        ):
            return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
