from __future__ import annotations

import csv
import hashlib
import json
import random
import re
import subprocess
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml
from pydantic import Field

from src.evaluation.metrics.structural import canonical_hash
from src.evaluation.structural_analysis import StructuralAnalysisConfig
from src.models.study_campaign import StudyCampaign, StudyModel, SubjectBinding
from src.models.swe_config import SweMcpConfig

WORKSPACE = Path(__file__).resolve().parents[2]
_ISSUE = re.compile(r"https://github\.com/([^/]+)/([^/]+)/issues/([1-9][0-9]*)/?$")
_MISSING = {"", "unknown", "null", "none"}


class CampaignJob(StudyModel):
    id: str
    study: str
    rq: str
    cohort: str
    slot: str
    set_index: int
    repetition: int
    variant: str
    condition: str
    worker: str
    block_key: str
    subject_id: str | None
    issue_url: str | None
    repo_path: str | None
    repository_key: str | None = None
    base_commit: str | None
    structural_config: str | None
    prompt: str | None
    issue_context_cutoff: str | None
    proposal_source_runs: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    runtime: SweMcpConfig


class CampaignPair(StudyModel):
    id: str
    study: str
    comparison: str
    block_key: str
    control_job: str
    treatment_job: str


class CampaignPlan(StudyModel):
    campaign: StudyCampaign
    manifest_path: str
    artifact_root: str
    ledger_path: str
    inputs: dict[str, str]
    input_trees: dict[str, list[str]] = Field(default_factory=dict)
    registry_audit: list[dict[str, Any]]
    jobs: list[CampaignJob]
    pairs: list[CampaignPair]
    plan_sha256: str = ""


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _resolve(root: Path, value: str) -> Path:
    return (root / value.replace("\\", "/")).resolve()


def _meaningful(value: str | None) -> str | None:
    text = (value or "").strip()
    return None if text.lower() in _MISSING else text


def _registry(path: Path) -> tuple[dict[str, dict[str, str]], list[dict[str, Any]]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.reader(stream))
    if not rows or len(set(rows[0])) != len(rows[0]):
        raise ValueError("Subject registry requires a unique CSV header.")
    header = rows[0]
    required = {
        "subject_id",
        "repo_owner",
        "repo_name",
        "is_legacy",
        "issue_url",
        "commit_sha",
    }
    if not required <= set(header):
        raise ValueError(
            f"Subject registry is missing columns: {sorted(required - set(header))}"
        )
    counts = Counter(row[0].strip() for row in rows[1:] if row)
    valid = {}
    audit = []
    for line, row in enumerate(rows[1:], 2):
        subject_id = row[0].strip() if row else ""
        errors = []
        if len(row) != len(header):
            errors.append(f"CSV has {len(row)} fields; expected {len(header)}.")
        if not subject_id or counts[subject_id] > 1:
            errors.append("Missing or duplicate subject ID.")
        record = dict(zip(header, row)) if not errors else {}
        if record:
            record = {key: value.strip() for key, value in record.items()}
            if not record["repo_owner"] or not record["repo_name"]:
                errors.append("Missing repository owner/name.")
        missing = [
            field
            for field in ("issue_url", "commit_sha")
            if not _meaningful(record.get(field))
        ]
        audit.append(
            {
                "line": line,
                "subject_id": subject_id,
                "errors": errors,
                "missing_anchor_fields": missing,
            }
        )
        if not errors:
            valid[subject_id] = record
    return valid, audit


def _proposals(
    path: Path,
    subjects: dict[str, dict[str, str]],
    rq: str,
    root: Path,
    inputs: dict[str, str],
) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {
            "run_id",
            "rq",
            "condition",
            "subject_id",
            "repo_owner",
            "repo_name",
            "issue_id",
            "experiment_config",
        }
        if not required <= set(reader.fieldnames or []):
            raise ValueError("Planned-run registry lacks required pairing columns.")
        groups: dict[tuple, list[dict]] = {}
        run_ids = set()
        for row in reader:
            if None in row or any(value is None for value in row.values()):
                raise ValueError("Planned-run registry has a malformed CSV row.")
            if row["run_id"] in run_ids:
                raise ValueError("Planned-run registry has duplicate run IDs.")
            run_ids.add(row["run_id"])
            if row["rq"] != rq:
                continue
            key = (
                row["subject_id"],
                row["repo_owner"],
                row["repo_name"],
                row["issue_id"],
            )
            groups.setdefault(key, []).append(row)
    proposals = []
    for (subject_id, owner, repo, issue), rows in groups.items():
        if len({row.get("comparison_group", "") for row in rows}) != 1:
            raise ValueError(
                "Proposed paired rows must belong to the same comparison group."
            )
        if len(rows) != 2 or {row["condition"] for row in rows} != {
            "baseline",
            "supervised",
        }:
            raise ValueError(
                "Proposed tasks require exactly one baseline and supervised row."
            )
        if not issue.isdigit() or int(issue) <= 0:
            raise ValueError("A planned issue ID is invalid.")
        subject = subjects.get(subject_id)
        if subject and (subject["repo_owner"], subject["repo_name"]) != (owner, repo):
            raise ValueError(
                "Planned task repository conflicts with its registered subject."
            )
        references = {row["experiment_config"].strip() for row in rows}
        if len(references) != 1 or not next(iter(references)):
            raise ValueError(
                "Paired rows must reference the same nonempty experiment_config."
            )
        configuration = _resolve(root, next(iter(references)))
        config_error = None
        binding = {}
        try:
            inputs[str(configuration)] = file_hash(configuration)
            binding = SubjectBinding.model_validate(
                yaml.safe_load(configuration.read_text(encoding="utf-8"))
            ).model_dump(exclude_unset=True)
            expected_url = f"https://github.com/{owner}/{repo}/issues/{issue}"
            if (
                binding.get("subject_id") != subject_id
                or binding.get("issue_url") != expected_url
            ):
                raise ValueError(
                    "Experiment configuration conflicts with its CSV subject/issue anchor."
                )
        except (OSError, ValueError, yaml.YAMLError) as error:
            config_error = f"Invalid experiment_config {configuration}: {error}"
            binding = {}
        proposals.append(
            {
                "subject_id": subject_id,
                "issue_url": f"https://github.com/{owner}/{repo}/issues/{issue}",
                "source_runs": [row["run_id"] for row in rows],
                "binding": binding,
                "config_error": config_error,
            }
        )
    return proposals


def _tree_files(root: Path) -> list[Path]:
    return sorted(
        path
        for path in root.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"
    )


def _pin_tree(inputs: dict[str, str], root: Path) -> list[str]:
    if not root.is_dir():
        raise ValueError(f"Required runtime data directory does not exist: {root}")
    paths = _tree_files(root)
    for path in paths:
        inputs[str(path.resolve())] = file_hash(path)
    return [str(path.resolve()) for path in paths]


def build_campaign_plan(manifest: Path) -> CampaignPlan:
    manifest = manifest.resolve()
    campaign = StudyCampaign.model_validate(
        yaml.safe_load(manifest.read_text(encoding="utf-8"))
    )
    root = _resolve(manifest.parent, campaign.config_root)
    inputs = {str(manifest): file_hash(manifest)}

    def pin(value: str) -> Path:
        path = _resolve(root, value)
        inputs[str(path)] = file_hash(path)
        return path

    subjects, audit = _registry(pin(campaign.subjects_registry))
    if (
        _resolve(root, campaign.available_models)
        != (WORKSPACE / "available_models.yaml").resolve()
    ):
        raise ValueError(
            "The worker currently requires the application-root available_models.yaml."
        )
    models = yaml.safe_load(pin(campaign.available_models).read_text(encoding="utf-8"))
    matches = [item for item in models if item["model_name"] == campaign.model.alias]
    if len(matches) != 1 or matches[0]["provider"] != campaign.model.provider:
        raise ValueError(
            "Model alias/provider must match exactly one available-model entry."
        )
    runtime = SweMcpConfig.model_validate(
        yaml.safe_load(pin(campaign.runtime_profile).read_text(encoding="utf-8"))
    )
    if runtime.semantic_index.neo4j_password:
        raise ValueError(
            "Campaign profiles must use credential environment references, not inline passwords."
        )
    runtime.execution = campaign.execution.repair
    runtime.verification = campaign.execution.verification
    trees = {str(WORKSPACE / "src"): _pin_tree(inputs, WORKSPACE / "src")}
    for directory in (
        runtime.knowledge_base.ground_data_dir or "knowledge/data",
        runtime.knowledge_base.linked_data_dir or "knowledge/linked_data",
        runtime.concern_assets.templates_root_dir or "knowledge/template",
        "templates/utils",
    ):
        tree = (WORKSPACE / directory).resolve()
        trees[str(tree)] = _pin_tree(inputs, tree)
    planned_path = (
        pin(campaign.planned_runs_registry) if campaign.planned_runs_registry else None
    )
    cohorts = {}
    for cohort_id, cohort in campaign.cohorts.items():
        proposed = (
            _proposals(planned_path, subjects, cohort.import_planned_rq, root, inputs)
            if (planned_path and cohort.import_planned_rq)
            else []
        )
        if cohort.import_planned_rq and not planned_path:
            raise ValueError("A planned-run import requires planned_runs_registry.")
        if cohort.legacy_only:
            proposed = [
                proposal
                for proposal in proposed
                if subjects.get(proposal["subject_id"], {}).get("is_legacy", "").lower()
                in {"yes", "true"}
            ]
        slots = [
            (f"set{group:02d}-task{task:02d}", group)
            for group in range(1, cohort.sets + 1)
            for task in range(1, cohort.tasks_per_set + 1)
        ]
        if len(proposed) > len(slots):
            raise ValueError(
                "Imported proposals exceed declared cohort capacity; refusing truncation."
            )
        resolved = []
        for index, (slot, group) in enumerate(slots):
            proposal = proposed[index] if index < len(proposed) else {}
            override = cohort.bindings.get(slot)
            values = {
                key: proposal[key]
                for key in ("subject_id", "issue_url")
                if key in proposal
            }
            values.update(proposal.get("binding", {}))
            values.update(override.model_dump(exclude_unset=True) if override else {})
            binding = SubjectBinding.model_validate(values)
            resolved.append(
                (
                    slot,
                    group,
                    binding,
                    proposal.get("source_runs", []),
                    proposal.get("config_error"),
                )
            )
        anchors = [
            (binding.subject_id, binding.issue_url)
            for _, _, binding, _, _ in resolved
            if binding.subject_id and binding.issue_url
        ]
        if len(anchors) != len(set(anchors)):
            raise ValueError(
                "Duplicate cohort tasks must use explicit study repetitions, not multiple slots."
            )
        cohorts[cohort_id] = resolved

    jobs = []
    pairs = []
    for study in campaign.studies:
        cohort = campaign.cohorts[study.cohort]
        for slot, set_index, binding, source_runs, config_error in cohorts[
            study.cohort
        ]:
            subject = subjects.get(binding.subject_id or "")
            common = []
            if config_error:
                common.append(config_error)
            if subject is None:
                common.append("Subject is unassigned or its registry row is invalid.")
            if (
                cohort.legacy_only
                and subject
                and subject["is_legacy"].lower() not in {"yes", "true"}
            ):
                common.append(
                    "Legacy cohort requires an explicitly legacy-marked subject."
                )
            if not binding.ai_use_approved:
                common.append("AI-tool use approval has not been recorded.")
            issue_url = binding.issue_url or (
                _meaningful(subject.get("issue_url")) if subject else None
            )
            issue = _ISSUE.fullmatch(issue_url or "")
            if not issue:
                common.append("Missing valid issue URL.")
            elif subject and (issue[1], issue[2]) != (
                subject["repo_owner"],
                subject["repo_name"],
            ):
                common.append("Issue URL conflicts with the registered repository.")
            base = binding.base_commit or (
                _meaningful(subject.get("commit_sha")) if subject else None
            )
            if not base or not re.fullmatch(r"[a-fA-F0-9]{40}", base):
                common.append("Missing pinned 40-character base commit.")
            repo = _resolve(root, binding.repo_path) if binding.repo_path else None
            repository_key = str(repo) if repo else None
            if repo is None or not repo.is_dir():
                common.append("Local repository path is missing or unavailable.")
            elif base and re.fullmatch(r"[a-fA-F0-9]{40}", base):
                result = subprocess.run(
                    ["git", "-C", str(repo), "cat-file", "-e", f"{base}^{{commit}}"],
                    capture_output=True,
                    check=False,
                )
                if result.returncode:
                    common.append(
                        "Pinned commit is unavailable in the local repository."
                    )
                else:
                    git_directory = subprocess.check_output(
                        ["git", "-C", str(repo), "rev-parse", "--git-common-dir"],
                        text=True,
                    ).strip()
                    repository_key = str((repo / git_directory).resolve())
            structural = None
            if not binding.structural_config:
                common.append(
                    "Missing pre-registered structural analyzer configuration."
                )
            else:
                try:
                    structural = pin(binding.structural_config)
                    analysis = StructuralAnalysisConfig.model_validate_json(
                        structural.read_text(encoding="utf-8")
                    )
                    for analyzer in analysis.analyzers:
                        if analyzer.enabled and analyzer.kind == "report":
                            for report in (
                                analyzer.before_report,
                                analyzer.after_report,
                            ):
                                pin(str(_resolve(structural.parent, report)))
                except (OSError, ValueError) as error:
                    common.append(f"Invalid structural analyzer configuration: {error}")
            if binding.issue_context_cutoff:
                cutoff = datetime.fromisoformat(
                    binding.issue_context_cutoff.replace("Z", "+00:00")
                )
                if cutoff.tzinfo is None or cutoff.utcoffset() is None:
                    raise ValueError("Issue context cutoff must include a timezone.")
            elif campaign.mode == "confirmatory":
                common.append(
                    "Confirmatory blocks require a historical evidence cutoff."
                )
            prompts = {}
            if any(variant != "original" for variant in study.variants):
                if not binding.paraphrases_file:
                    common.append("Missing human-authored paraphrase file.")
                else:
                    try:
                        prompts = json.loads(
                            pin(binding.paraphrases_file).read_text(encoding="utf-8")
                        )
                        expected = set(study.variants) - {"original"}
                        if (
                            not isinstance(prompts, dict)
                            or set(prompts) != expected
                            or any(
                                not isinstance(text, str) or not text.strip()
                                for text in prompts.values()
                            )
                        ):
                            raise ValueError(
                                "Paraphrase file must exactly cover the declared non-original variants."
                            )
                    except (OSError, ValueError) as error:
                        common.append(f"Invalid paraphrase file: {error}")
                        prompts = {}
            for repetition in range(1, study.repetitions + 1):
                for variant in study.variants:
                    block = (
                        f"{study.id}.{study.cohort}.{slot}.r{repetition:02d}.{variant}"
                    )
                    conditions = list(study.conditions)
                    seed = canonical_hash([campaign.execution.order_seed, block])
                    random.Random(int(seed, 16)).shuffle(conditions)
                    block_jobs = []
                    for condition in conditions:
                        resolved_runtime = runtime.model_copy(deep=True)
                        if condition.strictness is not None:
                            resolved_runtime.judging.strictness = condition.strictness
                        blockers = list(common)
                        if condition.worker != "mcp_supervised":
                            blockers.append(
                                "Prompt-only issue execution is not implemented; the reproducibility scaffold is not a valid worker."
                            )
                        job = CampaignJob(
                            id=f"{campaign.campaign_id}.{block}.{condition.id}",
                            study=study.id,
                            rq=study.rq,
                            cohort=study.cohort,
                            slot=slot,
                            set_index=set_index,
                            repetition=repetition,
                            variant=variant,
                            condition=condition.id,
                            worker=condition.worker,
                            block_key=block,
                            subject_id=binding.subject_id,
                            issue_url=issue_url,
                            repo_path=str(repo) if repo else None,
                            repository_key=repository_key,
                            base_commit=base,
                            structural_config=str(structural) if structural else None,
                            prompt=prompts.get(variant),
                            issue_context_cutoff=binding.issue_context_cutoff,
                            proposal_source_runs=source_runs,
                            blockers=blockers,
                            runtime=resolved_runtime,
                        )
                        block_jobs.append(job)
                    if campaign.execution.require_complete_blocks and any(
                        job.blockers for job in block_jobs
                    ):
                        for job in block_jobs:
                            if not job.blockers:
                                job.blockers.append(
                                    "A matched condition in this block is blocked."
                                )
                    by_condition = {job.condition: job.id for job in block_jobs}
                    jobs.extend(block_jobs)
                    for comparison in study.comparisons:
                        pairs.append(
                            CampaignPair(
                                id=f"{campaign.campaign_id}.{block}.{comparison.id}",
                                study=study.id,
                                comparison=comparison.id,
                                block_key=block,
                                control_job=by_condition[comparison.control],
                                treatment_job=by_condition[comparison.treatment],
                            )
                        )
    plan = CampaignPlan(
        campaign=campaign,
        manifest_path=str(manifest),
        artifact_root=str(_resolve(root, campaign.execution.artifact_root)),
        ledger_path=str(_resolve(root, campaign.execution.ledger)),
        inputs=inputs,
        input_trees=trees,
        registry_audit=audit,
        jobs=jobs,
        pairs=pairs,
    )
    plan.plan_sha256 = canonical_hash(
        plan.model_dump(mode="json", exclude={"plan_sha256"})
    )
    return plan


def verify_plan_inputs(plan: CampaignPlan) -> None:
    expected = canonical_hash(plan.model_dump(mode="json", exclude={"plan_sha256"}))
    if expected != plan.plan_sha256:
        raise ValueError("Frozen plan content does not match its SHA-256.")
    for directory, files in plan.input_trees.items():
        if [str(path.resolve()) for path in _tree_files(Path(directory))] != files:
            raise ValueError(
                f"Frozen runtime directory membership changed: {directory}"
            )
    for filename, digest in plan.inputs.items():
        path = Path(filename)
        if not path.is_file() or file_hash(path) != digest:
            raise ValueError(f"Frozen campaign input changed or is missing: {filename}")
