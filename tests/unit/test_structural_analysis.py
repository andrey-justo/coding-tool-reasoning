from __future__ import annotations

import json
import subprocess
import sys
from contextlib import contextmanager
from copy import deepcopy
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from src.evaluation.metrics.structural import (
    compare_structural_metrics,
    validate_metric_sources,
)
from src.evaluation.structural_analysis import (
    AnalyzerConfig,
    StructuralAnalysisConfig,
    _native_counts,
    _sloc,
    collect_reports,
    discover_analyzers,
    main,
    metric_input,
)
from src.experiments.issue_mcp_experiment import (
    _build_parser,
    _evaluate_structural_block,
)
from tests.unit.test_structural_metrics import (
    synthetic_input,
    synthetic_protocol,
    synthetic_report,
)


def _ruff_config() -> StructuralAnalysisConfig:
    protocol = synthetic_protocol()
    for rule, rule_id in zip(protocol["rules"], ["F401", "C901", "F841"], strict=True):
        rule["rule_id"] = rule_id
    version = (
        subprocess.check_output([sys.executable, "-m", "ruff", "--version"], text=True)
        .strip()
        .removeprefix("ruff ")
    )
    return StructuralAnalysisConfig.model_validate(
        {
            "protocol": protocol,
            "analyzers": [
                {
                    "instrument": "fixture",
                    "kind": "ruff",
                    "expected_version": version,
                    "ruleset_id": "synthetic-only",
                    "ruleset_version": "1",
                }
            ],
        }
    )


def test_discovery_reports_configuration_without_executing_it(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[tool.ruff]\nline-length=88\n")
    (tmp_path / "a.csproj").write_text("<Project/>")
    (tmp_path / "sonar-project.properties").write_text("sonar.projectKey=example\n")
    (tmp_path / ".venv").mkdir()
    (tmp_path / ".venv" / "hidden.csproj").write_text("<Project/>")
    assert discover_analyzers(tmp_path) == [
        {"kind": "ruff", "configuration": "pyproject.toml"},
        {"kind": "roslyn", "configuration": "a.csproj"},
        {"kind": "sonarqube", "configuration": "sonar-project.properties"},
    ]


def test_pyproject_without_ruff_is_not_a_ruff_configuration(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname='example'\n")
    assert discover_analyzers(tmp_path) == []


def test_sloc_excludes_comments_and_blank_lines_but_counts_code_on_comment_lines():
    assert _sloc("a.py", "# comment\n\nx = '# text'  # comment\n") == 1
    assert _sloc("a.cs", "// comment\n\nclass C { /* text */ int x; }\n") == 1
    with pytest.raises(ValueError, match="No live SLOC"):
        _sloc("a.cpp", "int x;")


def test_live_ruff_collection_and_source_linked_improvement(tmp_path):
    config = _ruff_config()
    before = {"a.py": "import os\n\ndef f():\n    unused = 1\n    return 2\n"}
    after = {"a.py": "def f():\n    return 2\n"}
    (tmp_path / "pyproject.toml").write_text("[tool.ruff]\nline-length=88\n")
    reports = []
    for stage, sources in (("before", before), ("after", after)):
        (tmp_path / "a.py").write_text(sources["a.py"], newline="")
        reports.append(collect_reports(config, stage, tmp_path, sources, tmp_path))
    inputs = metric_input(config, *reports)
    validate_metric_sources(inputs, before, after)
    result = compare_structural_metrics(inputs)
    assert result.before.raw_counts == {"solid": 1, "arch": 0, "smell": 1}
    assert result.after.raw_counts == {"solid": 0, "arch": 0, "smell": 0}
    assert result.delta_struct == 1
    assert result.effectiveness_verdict == "improved"
    assert result.before.loc == 4
    assert (tmp_path / "a.py").read_text() == after["a.py"]


def test_live_version_mismatch_is_not_reported_as_clean(tmp_path):
    config = _ruff_config()
    config.analyzers[0].expected_version = "not-installed"
    (tmp_path / "a.py").write_text("x = 1\n", newline="")
    with pytest.raises(ValueError, match="pinned version"):
        collect_reports(config, "before", tmp_path, {"a.py": "x = 1\n"}, tmp_path)


def test_normalized_report_import_and_provenance(tmp_path):
    config = StructuralAnalysisConfig.model_validate(
        {
            "protocol": synthetic_protocol(),
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
    )
    (tmp_path / "before.json").write_text(json.dumps(synthetic_report()))
    report = collect_reports(config, "before", tmp_path, {"a.py": "before"}, tmp_path)[
        0
    ]
    assert report.source == "synthetic-test-report"
    config.analyzers[0].expected_version = "2"
    with pytest.raises(ValueError, match="provenance"):
        collect_reports(config, "before", tmp_path, {"a.py": "before"}, tmp_path)


def _sarif():
    return {
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "synthetic-Roslyn",
                        "version": "1",
                        "rules": [{"id": "S"}, {"id": "A"}, {"id": "M"}],
                    }
                },
                "artifacts": [{"location": {"uri": "a.cs"}}],
                "invocations": [{"executionSuccessful": True}],
                "results": [
                    {
                        "ruleId": "A",
                        "locations": [
                            {"physicalLocation": {"artifactLocation": {"uri": "a.cs"}}}
                        ],
                    }
                ],
            }
        ],
    }


def test_roslyn_sarif_counts_and_rejects_missing_coverage(tmp_path):
    payload = _sarif()
    counts = _native_counts(payload, "roslyn", tmp_path, {"a.cs"}, {"S", "A", "M"}, "1")
    assert [count.model_dump() for count in counts] == [
        {"rule_id": "A", "path": "a.cs", "count": 1}
    ]
    for field in ("artifacts", "invocations"):
        broken = deepcopy(payload)
        broken["runs"][0].pop(field)
        with pytest.raises(ValueError, match="attest"):
            _native_counts(broken, "roslyn", tmp_path, {"a.cs"}, {"S", "A", "M"}, "1")
    payload["runs"][0]["results"][0]["suppressions"] = [{"kind": "inSource"}]
    with pytest.raises(ValueError, match="Suppressed"):
        _native_counts(payload, "roslyn", tmp_path, {"a.cs"}, {"S", "A", "M"}, "1")


def test_sarif_uri_encoding_and_base_are_resolved_before_scope_filtering(tmp_path):
    payload = _sarif()
    run = payload["runs"][0]
    run["originalUriBaseIds"] = {"ROOT": {"uri": tmp_path.as_uri() + "/"}}
    location = {"uri": "with%20space.cs", "uriBaseId": "ROOT"}
    run["artifacts"][0]["location"] = location
    run["results"][0]["locations"][0]["physicalLocation"]["artifactLocation"] = {
        "index": 0
    }
    counts = _native_counts(
        payload, "roslyn", tmp_path, {"with space.cs"}, {"S", "A", "M"}, "1"
    )
    assert counts[0].path == "with space.cs"


@pytest.mark.parametrize(
    "case", ["disabled", "execution-error", "pass-result", "absent-result", "override"]
)
def test_sarif_does_not_count_disabled_or_non_violation_evidence(tmp_path, case):
    payload = _sarif()
    run = payload["runs"][0]
    if case == "disabled":
        run["tool"]["driver"]["rules"][0]["defaultConfiguration"] = {"enabled": False}
    elif case == "execution-error":
        run["invocations"][0]["toolExecutionNotifications"] = [{"level": "error"}]
    elif case == "pass-result":
        run["results"][0]["kind"] = "pass"
    elif case == "absent-result":
        run["results"][0]["baselineState"] = "absent"
    else:
        run["invocations"][0]["ruleConfigurationOverrides"] = [
            {
                "descriptor": {"id": "S"},
                "configuration": {"enabled": False},
            }
        ]
    with pytest.raises(ValueError):
        _native_counts(payload, "roslyn", tmp_path, {"a.cs"}, {"S", "A", "M"}, "1")


def test_live_roslyn_command_produces_sarif_and_cleans_report(tmp_path, monkeypatch):
    config = StructuralAnalysisConfig.model_validate(
        {
            "protocol": synthetic_protocol(),
            "analyzers": [
                {
                    "instrument": "fixture",
                    "kind": "roslyn",
                    "expected_version": "1",
                    "ruleset_id": "synthetic",
                    "ruleset_version": "1",
                    "command": ["dotnet", "build", "-p:ErrorLog={report}"],
                }
            ],
        }
    )
    source = "class C { }\n"
    (tmp_path / "a.cs").write_text(source, newline="")

    def run(command, repo, timeout):
        assert command[0:2] == ["dotnet", "build"]
        (repo / ".structural-analysis.sarif").write_text(json.dumps(_sarif()))
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("src.evaluation.structural_analysis._run", run)
    report = collect_reports(config, "before", tmp_path, {"a.cs": source}, tmp_path)[0]
    assert report.counts[0].rule_id == "A"
    assert not (tmp_path / ".structural-analysis.sarif").exists()


def test_sonar_collection_is_opt_in_and_checks_exact_remote_sources(
    tmp_path, monkeypatch
):
    config = StructuralAnalysisConfig.model_validate(
        {
            "protocol": synthetic_protocol(),
            "analyzers": [
                {
                    "instrument": "fixture",
                    "kind": "sonarqube",
                    "expected_version": "1",
                    "ruleset_id": "synthetic",
                    "ruleset_version": "1",
                    "sonar_url": "https://sonar.invalid",
                    "sonar_project": "example",
                    "sonar_before_branch": "before",
                    "sonar_after_branch": "after",
                }
            ],
        }
    )
    source = "x = 1\n"
    calls = []

    class Session:
        auth = None

        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def get(self, url, params, timeout):
            calls.append((url, params))
            payload = None
            text = ""
            if url.endswith("/server/version"):
                text = "1"
            elif url.endswith("/project_analyses/search"):
                payload = {
                    "analyses": [{"key": "snapshot", "date": "2026-01-02T00:00:00Z"}]
                }
            elif url.endswith("/plugins/installed"):
                payload = {"plugins": [{"key": "python", "version": "1"}]}
            elif url.endswith("/qualityprofiles/search"):
                payload = {
                    "profiles": [
                        {"key": "profile", "rulesUpdatedAt": "2026-01-01T00:00:00Z"}
                    ]
                }
            elif url.endswith("/rules/search"):
                payload = {"rules": [{"key": r} for r in ("S", "A", "M")], "total": 3}
            elif url.endswith("/sources/raw"):
                text = source
            elif url.endswith("/issues/search"):
                assert params["componentKeys"] == "example:a.py"
                payload = {
                    "issues": [{"rule": "S", "component": "example:a.py"}],
                    "paging": {"total": 1, "pageSize": 500},
                }
            else:
                pytest.fail(f"Unexpected endpoint: {url}")
            return SimpleNamespace(
                text=text,
                json=lambda: payload,
                raise_for_status=lambda: None,
            )

    monkeypatch.setenv("SONAR_TOKEN", "test-only")
    monkeypatch.setattr("src.evaluation.structural_analysis.requests.Session", Session)
    report = collect_reports(config, "before", tmp_path, {"a.py": source}, tmp_path)[0]
    assert report.counts[0].count == 1
    assert "test-only" not in report.model_dump_json()
    with pytest.raises(ValueError, match="Stale SonarQube source"):
        collect_reports(config, "after", tmp_path, {"a.py": "changed"}, tmp_path)
    monkeypatch.delenv("SONAR_TOKEN")
    with pytest.raises(ValueError, match="credential"):
        collect_reports(config, "before", tmp_path, {"a.py": source}, tmp_path)


def test_incomplete_configuration_is_rejected():
    with pytest.raises(ValidationError, match="explicit build command"):
        AnalyzerConfig(
            instrument="r",
            kind="roslyn",
            expected_version="1",
            ruleset_id="r",
            ruleset_version="1",
        )
    with pytest.raises(ValidationError, match="both analysis branches"):
        AnalyzerConfig(
            instrument="s",
            kind="sonarqube",
            expected_version="1",
            ruleset_id="s",
            ruleset_version="1",
        )


def test_runner_uses_separate_snapshots_and_validates_actual_sources(
    tmp_path, monkeypatch
):
    config = _ruff_config()
    config_path = tmp_path / "analysis.json"
    config_path.write_text(config.model_dump_json())
    snapshots = []

    @contextmanager
    def snapshot(*_):
        path = tmp_path / f"snapshot-{len(snapshots)}"
        path.mkdir()
        snapshots.append(path)
        yield path

    monkeypatch.setattr(
        "src.experiments.issue_mcp_experiment._base_ref_worktree", snapshot
    )
    result = _evaluate_structural_block(
        str(config_path),
        tmp_path,
        "base",
        {"a.py": "import os\n"},
        {"a.py": "x = 1\n"},
        [],
    )
    assert len(snapshots) == 2
    assert result["comparison"]["effectiveness_verdict"] == "improved"
    assert result["comparison"]["evidence"]["after"][0]["files"][0]["loc"] == 1
    assert (
        _evaluate_structural_block(None, tmp_path, "base", {}, {}, [])["status"]
        == "not-run"
    )
    args = _build_parser().parse_args(
        [
            "--issue-url",
            "https://github.com/o/r/issues/1",
            "--repo-path",
            str(tmp_path),
            "--structural-analysis-config",
            str(config_path),
        ]
    )
    assert args.structural_analysis_config == str(config_path)


def test_discovery_and_ci_regression_cli(tmp_path, capsys):
    assert main(["--discover-repo", str(tmp_path)]) == 0
    assert json.loads(capsys.readouterr().out)["execution"] == "not-requested"
    source = tmp_path / "input.json"
    output = tmp_path / "result.json"
    source.write_text(synthetic_input((0, 0, 0), (1, 0, 0)).model_dump_json())
    assert (
        main(["--input", str(source), "--output", str(output), "--fail-on-regression"])
        == 1
    )
    result = json.loads(output.read_text())
    assert result["delta_struct"] == -1
    assert result["effectiveness_verdict"] == "regressed"
    assert main(["--input", str(source), "--output", str(output)]) == 0
    schema = tmp_path / "schema.json"
    assert main(["--config-schema", "--output", str(schema)]) == 0
    assert "protocol" in json.loads(schema.read_text())["properties"]


def test_live_collection_rejects_mismatched_on_disk_sources(tmp_path):
    config = _ruff_config()
    (tmp_path / "a.py").write_text("import os\n", newline="")
    with pytest.raises(ValueError, match="requested source snapshot"):
        collect_reports(config, "before", tmp_path, {"a.py": "x = 1\n"}, tmp_path)


def test_runner_collects_in_real_worktrees_and_preserves_original_repo(tmp_path):
    repo = tmp_path / "subject"
    repo.mkdir()
    (repo / "a.py").write_text("import os\n", newline="")
    (repo / "pyproject.toml").write_text("[tool.ruff]\nline-length=88\n")
    subprocess.run(["git", "init", str(repo)], check=True, capture_output=True)
    for key, value in (
        ("core.autocrlf", "false"),
        ("core.safecrlf", "false"),
        ("commit.gpgsign", "false"),
    ):
        subprocess.run(
            ["git", "-C", str(repo), "config", key, value],
            check=True,
            capture_output=True,
        )
    subprocess.run(
        ["git", "-C", str(repo), "add", "."], check=True, capture_output=True
    )
    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "-c",
            "user.name=Metric Fixture",
            "-c",
            "user.email=fixture@example.invalid",
            "commit",
            "-m",
            "Synthetic metric fixture\n\nCo-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>",
        ],
        check=True,
        capture_output=True,
    )
    config = _ruff_config()
    config_path = tmp_path / "config.json"
    config_path.write_text(config.model_dump_json())
    logs = []
    result = _evaluate_structural_block(
        str(config_path),
        repo,
        "HEAD",
        {"a.py": "import os\n"},
        {"a.py": "x = 1\n"},
        logs,
    )
    assert result["comparison"]["delta_struct"] == 1
    assert (repo / "a.py").read_text() == "import os\n"
    assert (
        subprocess.check_output(
            ["git", "-C", str(repo), "status", "--porcelain"], text=True
        )
        == ""
    )
    listing = subprocess.check_output(
        ["git", "-C", str(repo), "worktree", "list", "--porcelain"], text=True
    )
    assert listing.count("worktree ") == 1
