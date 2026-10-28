from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.mcp.tools.verify_testability_gate_tool import VerifyTestabilityGateTool


def _dummy_registry():
    return object()


def test_parse_junit_totals_for_testsuite(tmp_path: Path) -> None:
    suite_file = tmp_path / "suite.xml"
    suite_file.write_text(
        '<testsuite tests="5" failures="1" errors="1" skipped="1" />',
        encoding="utf-8",
    )

    totals = VerifyTestabilityGateTool._parse_junit_totals(suite_file)
    assert totals == {
        "tests": 5,
        "failures": 1,
        "errors": 1,
        "skipped": 1,
        "passed": 2,
    }


@pytest.mark.parametrize("prerequisite_status", ["pass", "fail", "timeout"])
def test_prerequisite_failure_stops_full_build_and_tests(
    monkeypatch,
    tmp_path,
    prerequisite_status,
):
    tool = VerifyTestabilityGateTool(_dummy_registry())
    monkeypatch.setattr(
        "src.mcp.tools.verify_testability_gate_tool.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout="", stderr=""),
    )
    monkeypatch.setattr(
        tool,
        "_discover_verification_commands",
        lambda **kwargs: {
            "project_type": "unknown",
            "pre_build_commands": [["prepare"]],
            "build_command": ["build"],
            "test_command": ["test"],
        },
    )
    calls = []

    def run(command, cwd, timeout_seconds):
        calls.append((command, timeout_seconds))
        status = prerequisite_status if command == ["prepare"] else "pass"
        return {
            "status": status,
            "exit_code": 0 if status == "pass" else 1,
            "duration_seconds": 2.0,
            "stdout_tail": "" if status == "pass" else "prepare failed",
            "stderr_tail": "",
            "timed_out": status == "timeout",
        }

    monkeypatch.setattr(tool, "_run_command_with_timeout", run)
    result = tool.execute(str(tmp_path), "HEAD", {}, timeout_seconds=20)
    build = result["build"]
    if prerequisite_status == "pass":
        assert [command for command, _ in calls] == [["prepare"], ["build"], ["test"]]
        assert build["completed_stages"] == 2
        assert build["stage"] == "full"
        assert build["duration_seconds"] == 4.0
        assert result["test"]["status"] == "pass"
    else:
        assert [command for command, _ in calls] == [["prepare"]]
        assert build["status"] == prerequisite_status
        assert build["completed_stages"] == 0
        assert build["stage"] == "prerequisite"
        assert build["command"] == ["prepare"]
        assert result["test"]["status"] == "not-run"
    assert all(0 < seconds <= 20 for _, seconds in calls)
    assert len(build["stages"]) == (2 if prerequisite_status == "pass" else 1)


def test_capture_preserves_errors_outside_console_tail_and_generated_source(tmp_path):
    source = tmp_path / "obj" / "Generated.g.cs"
    source.parent.mkdir()
    source.write_text(
        "public class Generated {\n void Run() { Missing(); }\n}\n", encoding="utf-8"
    )
    output = (
        f"{source}(2,15): error CS0103: The name 'Missing' does not exist [App.csproj]\n"
        + "\n".join(f"informational line {index}" for index in range(50))
    )
    assert "CS0103" not in VerifyTestabilityGateTool._tail_text(output)
    diagnostics = VerifyTestabilityGateTool._capture_build_diagnostics(
        {"stdout": output, "stdout_tail": VerifyTestabilityGateTool._tail_text(output)},
        tmp_path,
        "dotnet",
        ["App.cs"],
    )
    assert len(diagnostics) == 1
    assert diagnostics[0]["relative_file"] == "obj/Generated.g.cs"
    assert "Missing();" in diagnostics[0]["source_excerpt"]
    assert "Run" in {item["name"] for item in diagnostics[0]["generated_declarations"]}
    assert diagnostics[0]["generated_declarations_truncated"] is False


def test_focused_compilation_keeps_all_overlays_but_skips_tests(monkeypatch, tmp_path):
    tool = VerifyTestabilityGateTool(_dummy_registry())
    monkeypatch.setattr(
        "src.mcp.tools.verify_testability_gate_tool.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout="", stderr=""),
    )
    commands = []

    def discover(**kwargs):
        assert kwargs["changed_files"] == ["src/A.cs"]
        assert (kwargs["repo_path"] / "src" / "A.cs").read_text() == "class A {}"
        assert (kwargs["repo_path"] / "src" / "B.cs").read_text() == "class B {}"
        return {
            "project_type": "dotnet",
            "pre_build_commands": [["prepare"]],
            "build_command": ["build"],
            "test_command": ["test"],
        }

    def run(command, **kwargs):
        commands.append(command)
        return {
            "status": "pass",
            "exit_code": 0,
            "duration_seconds": 0.1,
            "stdout_tail": "",
            "stderr_tail": "",
            "timed_out": False,
        }

    monkeypatch.setattr(tool, "_discover_verification_commands", discover)
    monkeypatch.setattr(tool, "_run_command_with_timeout", run)
    result = tool.execute(
        str(tmp_path),
        "HEAD",
        {"src/A.cs": "class A {}", "src/B.cs": "class B {}"},
        focus_files=["src/A.cs"],
        compile_only=True,
    )
    assert commands == [["prepare"], ["build"]]
    assert result["verification_scope"] == "focused"
    assert result["test"]["status"] == "not-run"
    assert result["compile_only"] is True
    assert "full verification is still required" in result["testability_gate"]["reason"]


@pytest.mark.parametrize("focus", [[], ["outside.cs"]])
def test_focused_verification_rejects_empty_or_unknown_targets(tmp_path, focus):
    with pytest.raises(ValueError, match="nonempty files"):
        VerifyTestabilityGateTool(_dummy_registry()).execute(
            str(tmp_path),
            "HEAD",
            {"known.cs": "class Known {}"},
            focus_files=focus,
        )


def test_capture_never_reads_source_outside_verification_worktree(tmp_path):
    source = tmp_path / "outside.cs"
    source.write_text("not part of this verification", encoding="utf-8")
    worktree = tmp_path / "worktree"
    worktree.mkdir()
    diagnostics = VerifyTestabilityGateTool._capture_build_diagnostics(
        {"stdout": f"{source}(1,1): error CS0103: missing [App.csproj]"},
        worktree,
        "dotnet",
        ["App.cs"],
    )
    assert len(diagnostics) == 1
    assert "source_excerpt" not in diagnostics[0]


def test_staged_verification_runs_real_python_compilation(monkeypatch, tmp_path):
    tool = VerifyTestabilityGateTool(_dummy_registry())
    real_run = subprocess.run

    def run(command, *args, **kwargs):
        if command[0] == "git":
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        return real_run(command, *args, **kwargs)

    monkeypatch.setattr(
        "src.mcp.tools.verify_testability_gate_tool.subprocess.run", run
    )
    monkeypatch.setattr(
        tool,
        "_discover_verification_commands",
        lambda **kwargs: {
            "project_type": "python",
            "pre_build_commands": [
                [sys.executable, "-m", "py_compile", "src/generated.py"]
            ],
            "build_command": [sys.executable, "-c", "print('full-build')"],
            "test_command": None,
        },
    )
    failed = tool.execute(
        str(tmp_path),
        "HEAD",
        {"src/generated.py": "def broken(:\n    pass\n"},
        20,
    )
    assert failed["build"]["status"] == "fail"
    assert failed["build"]["stage"] == "prerequisite"
    assert len(failed["build"]["stages"]) == 1
    assert failed["build"]["diagnostics"][0]["relative_file"] == "src/generated.py"
    assert "def broken(" in failed["build"]["diagnostics"][0]["source_excerpt"]
    passed = tool.execute(
        str(tmp_path),
        "HEAD",
        {"src/generated.py": "def fixed():\n    return 1\n"},
        20,
    )
    assert passed["build"]["status"] == "pass"
    assert passed["build"]["completed_stages"] == 2
    assert "full-build" in passed["build"]["stdout_tail"]


def test_build_stages_share_one_timeout_budget(monkeypatch, tmp_path):
    tool = VerifyTestabilityGateTool(_dummy_registry())
    monkeypatch.setattr(
        "src.mcp.tools.verify_testability_gate_tool.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout="", stderr=""),
    )
    monkeypatch.setattr(
        tool,
        "_discover_verification_commands",
        lambda **kwargs: {
            "project_type": "unknown",
            "pre_build_commands": [["prepare"]],
            "build_command": ["build"],
            "test_command": None,
        },
    )
    times = iter([10.0, 12.0, 17.0])
    monkeypatch.setattr(
        "src.mcp.tools.verify_testability_gate_tool.time.monotonic",
        lambda: next(times),
    )
    budgets = []

    def run(command, cwd, timeout_seconds):
        budgets.append(timeout_seconds)
        return {"status": "pass", "duration_seconds": 1.0}

    monkeypatch.setattr(tool, "_run_command_with_timeout", run)
    tool.execute(str(tmp_path), "HEAD", {}, timeout_seconds=10)
    assert budgets == [8.0, 3.0]


def test_parse_junit_totals_for_testsuites(tmp_path: Path) -> None:
    suites_file = tmp_path / "suites.xml"
    suites_file.write_text(
        """
        <testsuites>
          <testsuite tests="3" failures="1" errors="0" skipped="1" />
          <testsuite tests="2" failures="0" errors="1" skipped="0" />
        </testsuites>
        """,
        encoding="utf-8",
    )
    totals = VerifyTestabilityGateTool._parse_junit_totals(suites_file)
    assert totals == {
        "tests": 5,
        "failures": 1,
        "errors": 1,
        "skipped": 1,
        "passed": 2,
    }


def test_parse_junit_totals_handles_missing_invalid_or_unknown_root(
    tmp_path: Path,
) -> None:
    missing = tmp_path / "missing.xml"
    assert VerifyTestabilityGateTool._parse_junit_totals(missing) is None

    invalid = tmp_path / "invalid.xml"
    invalid.write_text("<testsuite>", encoding="utf-8")
    assert VerifyTestabilityGateTool._parse_junit_totals(invalid) is None

    unknown = tmp_path / "unknown.xml"
    unknown.write_text("<root />", encoding="utf-8")
    assert VerifyTestabilityGateTool._parse_junit_totals(unknown) is None


def test_run_command_with_timeout_covers_pass_fail_and_timeout(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    class _Completed:
        def __init__(self, returncode: int, stdout: str, stderr: str) -> None:
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

    calls = {"count": 0}

    def _fake_run(*_args, **_kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            return _Completed(0, "ok\n", "")
        if calls["count"] == 2:
            return _Completed(3, "", "failed\n")
        raise subprocess.TimeoutExpired(
            cmd=["x"], timeout=1, output="a\n", stderr="b\n"
        )

    monkeypatch.setattr(
        "src.mcp.tools.verify_testability_gate_tool.subprocess.run",
        _fake_run,
    )

    passed = VerifyTestabilityGateTool._run_command_with_timeout(["x"], tmp_path, 1)
    failed = VerifyTestabilityGateTool._run_command_with_timeout(["y"], tmp_path, 1)
    timed_out = VerifyTestabilityGateTool._run_command_with_timeout(["z"], tmp_path, 1)

    assert passed["status"] == "pass"
    assert passed["exit_code"] == 0
    assert failed["status"] == "fail"
    assert failed["exit_code"] == 3
    assert timed_out["status"] == "timeout"
    assert timed_out["timed_out"] is True
    assert timed_out["stdout_tail"] == "a"
    assert timed_out["stderr_tail"] == "b"


def test_discover_verification_commands_for_python_and_unknown(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    py_repo = tmp_path / "py_repo"
    (py_repo / "src").mkdir(parents=True)
    (py_repo / "tests").mkdir()
    (py_repo / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")

    monkeypatch.setattr(
        "src.service.code_sanitization.python_strategy.shutil.which", lambda _: None
    )

    junit = py_repo / ".experiment_artifacts" / "junit.xml"
    cov = py_repo / ".experiment_artifacts" / "coverage.xml"
    discovered = VerifyTestabilityGateTool._discover_verification_commands(
        py_repo, junit, cov
    )
    assert discovered["project_type"] == "python"
    assert discovered["build_command"] == [
        sys.executable,
        "-m",
        "compileall",
        "-q",
        "src",
    ]
    assert isinstance(discovered["test_command"], list)

    unknown_repo = tmp_path / "unknown_repo"
    unknown_repo.mkdir()
    unknown = VerifyTestabilityGateTool._discover_verification_commands(
        unknown_repo, junit, cov
    )
    assert unknown["project_type"] == "unknown"
    assert unknown["build_command"] is None
    assert unknown["test_command"] is None


def test_discover_verification_commands_for_dotnet_changed_project(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "dotnet_repo"
    changed_project = repo / "src" / "Core"
    test_project = repo / "src" / "Core.Tests"
    changed_project.mkdir(parents=True)
    test_project.mkdir(parents=True)
    (repo / "Product.slnx").write_text("<Solution />", encoding="utf-8")
    (changed_project / "Core.csproj").write_text("<Project />", encoding="utf-8")
    (changed_project / "Changed.cs").write_text("class Changed {}", encoding="utf-8")
    (test_project / "Core.Tests.csproj").write_text(
        "<Project />",
        encoding="utf-8",
    )

    artifacts = repo / ".experiment_artifacts"
    discovered = VerifyTestabilityGateTool._discover_verification_commands(
        repo,
        artifacts / "junit.xml",
        artifacts / "coverage.xml",
        changed_files=["src/Core/Changed.cs"],
    )

    assert discovered["project_type"] == "dotnet"
    assert discovered["build_command"][:2] == ["dotnet", "build"]
    assert "gate-targets.proj" in discovered["build_command"][2]
    assert discovered["test_command"][:2] == ["dotnet", "test"]
    assert discovered["test_command"][2] == str(
        (test_project / "Core.Tests.csproj").relative_to(repo)
    )


def test_execute_returns_reason_when_worktree_add_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    tool = VerifyTestabilityGateTool(_dummy_registry())

    class _Completed:
        def __init__(self, returncode: int, stdout: str = "", stderr: str = "") -> None:
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

    monkeypatch.setattr(
        "src.mcp.tools.verify_testability_gate_tool.subprocess.run",
        lambda *_args, **_kwargs: _Completed(1, stderr="cannot add worktree"),
    )

    result = tool.execute(
        repo_path=str(tmp_path),
        base_ref="HEAD",
        generated_code_by_file={},
        timeout_seconds=10,
    )

    assert result["testability_gate"]["build_status"] == "not-run"
    assert result["testability_gate"]["test_status"] == "not-run"
    assert "Could not create temporary worktree" in result["testability_gate"]["reason"]


def test_execute_success_path_populates_gate_and_metrics(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    tool = VerifyTestabilityGateTool(_dummy_registry())
    real_run = subprocess.run

    class _Completed:
        def __init__(self, returncode: int, stdout: str = "", stderr: str = "") -> None:
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

    def _patched_run(command, *args, **kwargs):
        if command[:4] == ["git", "-C", str(tmp_path.resolve()), "worktree"]:
            return _Completed(0)
        return real_run(command, *args, **kwargs)

    def _discover(
        *,
        repo_path: Path,
        junit_xml_path: Path,
        coverage_xml_path: Path,
        changed_files: list[str] | None = None,
        verification_config: object = None,
    ):
        del repo_path
        del changed_files
        del verification_config
        build = [sys.executable, "-c", "print('build-ok')"]
        test_script = (
            "from pathlib import Path;"
            f'Path(r\'{junit_xml_path}\').write_text(\'<testsuite tests="4" failures="1" errors="0" skipped="1" />\', encoding=\'utf-8\');'
            f"Path(r'{coverage_xml_path}').write_text('<coverage/>', encoding='utf-8');"
            "print('test-ok')"
        )
        test = [sys.executable, "-c", test_script]
        return {"project_type": "python", "build_command": build, "test_command": test}

    monkeypatch.setattr(
        "src.mcp.tools.verify_testability_gate_tool.subprocess.run",
        _patched_run,
    )
    monkeypatch.setattr(
        VerifyTestabilityGateTool,
        "_discover_verification_commands",
        staticmethod(_discover),
    )

    result = tool.execute(
        repo_path=str(tmp_path),
        base_ref="HEAD",
        generated_code_by_file={"src/generated.py": "print('hello')\n"},
        timeout_seconds=20,
    )

    assert result["build"]["status"] == "pass"
    assert result["test"]["status"] == "pass"
    assert result["coverage"]["available"] is True
    assert result["junit"]["available"] is True
    assert result["test_pass_rate_source"] == "junit_xml"
    assert result["test_pass_rate"]["total"] == 4
    assert result["test_pass_rate"]["passed"] == 2
    assert result["testability_gate"]["reason"].startswith("Build and tests passed")


def test_execute_reason_when_tests_fail_and_when_no_commands(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    tool = VerifyTestabilityGateTool(_dummy_registry())
    real_run = subprocess.run

    class _Completed:
        def __init__(self, returncode: int, stdout: str = "", stderr: str = "") -> None:
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

    def _patched_run(command, *args, **kwargs):
        if command[:4] == ["git", "-C", str(tmp_path.resolve()), "worktree"]:
            return _Completed(0)
        return real_run(command, *args, **kwargs)

    monkeypatch.setattr(
        "src.mcp.tools.verify_testability_gate_tool.subprocess.run",
        _patched_run,
    )

    def _discover_with_failing_tests(
        *,
        repo_path: Path,
        junit_xml_path: Path,
        coverage_xml_path: Path,
        changed_files: list[str] | None = None,
        verification_config: object = None,
    ):
        del repo_path
        del changed_files
        del verification_config
        del junit_xml_path, coverage_xml_path
        build = [sys.executable, "-c", "print('build-ok')"]
        test = [sys.executable, "-c", "import sys; sys.exit(2)"]
        return {"project_type": "python", "build_command": build, "test_command": test}

    monkeypatch.setattr(
        VerifyTestabilityGateTool,
        "_discover_verification_commands",
        staticmethod(_discover_with_failing_tests),
    )
    failing = tool.execute(
        repo_path=str(tmp_path),
        base_ref="HEAD",
        generated_code_by_file={},
        timeout_seconds=20,
    )
    assert failing["testability_gate"]["test_status"] == "fail"
    assert "Tests failed or timed out" in failing["testability_gate"]["reason"]

    monkeypatch.setattr(
        VerifyTestabilityGateTool,
        "_discover_verification_commands",
        staticmethod(
            lambda *,
            repo_path,
            junit_xml_path,
            coverage_xml_path,
            changed_files=None,
            verification_config=None: {
                "project_type": "unknown",
                "build_command": None,
                "test_command": None,
            }
        ),
    )
    no_cmd = tool.execute(
        repo_path=str(tmp_path),
        base_ref="HEAD",
        generated_code_by_file={},
        timeout_seconds=20,
    )
    assert no_cmd["testability_gate"]["build_status"] == "not-run"
    assert no_cmd["testability_gate"]["test_status"] == "not-run"
    assert (
        no_cmd["testability_gate"]["reason"]
        == "No build/test command discovered for this repository."
    )


def test_parse_trx_totals_from_real_dotnet_results(tmp_path: Path) -> None:
    trx_path = tmp_path / "junit.trx"
    trx_path.write_text(
        '<TestRun xmlns="http://microsoft.com/schemas/VisualStudio/TeamTest/2010">'
        '<ResultSummary outcome="Completed">'
        '<Counters total="1894" executed="1860" passed="1860" failed="0" error="0"'
        ' timeout="0" aborted="0" />'
        "</ResultSummary></TestRun>",
        encoding="utf-8",
    )

    totals = VerifyTestabilityGateTool._parse_trx_totals(trx_path)

    assert totals == {
        "tests": 1894,
        "failures": 0,
        "errors": 0,
        "skipped": 34,
        "passed": 1860,
    }


def test_parse_trx_totals_returns_none_for_missing_file(tmp_path: Path) -> None:
    assert VerifyTestabilityGateTool._parse_trx_totals(tmp_path / "absent.trx") is None


def test_preserve_artifact_copies_file_out_of_the_disposable_worktree(
    tmp_path: Path,
) -> None:
    worktree_artifact = tmp_path / "worktree" / "junit.trx"
    worktree_artifact.parent.mkdir(parents=True)
    worktree_artifact.write_text("<TestRun />", encoding="utf-8")

    log_lines: list[str] = []
    preserved = VerifyTestabilityGateTool._preserve_artifact(
        worktree_artifact, log_lines
    )

    shutil.rmtree(worktree_artifact.parent)

    assert Path(preserved) != worktree_artifact
    assert Path(preserved).exists()
    assert Path(preserved).read_text(encoding="utf-8") == "<TestRun />"
    assert log_lines == []
    shutil.rmtree(Path(preserved).parent)


def test_preserve_artifact_falls_back_to_the_original_path_on_failure(
    tmp_path: Path,
) -> None:
    missing = tmp_path / "absent.trx"

    log_lines: list[str] = []
    preserved = VerifyTestabilityGateTool._preserve_artifact(missing, log_lines)

    assert preserved == str(missing)
    assert log_lines and "absent.trx" in log_lines[0]
