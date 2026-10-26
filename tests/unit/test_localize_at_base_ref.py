from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from src.experiments.issue_mcp_experiment import _localize_at_base_ref
from src.service.localizer import RepositoryIssueLocalizer


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        text=True,
        capture_output=True,
        check=True,
    )
    return result.stdout.strip()


@pytest.fixture()
def repo_with_history(tmp_path: Path) -> tuple[Path, str]:
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    _git(repo.parent, "init", "repo")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")

    base_file = repo / "src" / "WidgetRegistry.py"
    base_file.write_text("class WidgetRegistry:\n    pass\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "base")
    base_ref = _git(repo, "rev-parse", "HEAD")

    # The working tree moves on: the file relevant to the issue is gone.
    base_file.unlink()
    (repo / "src" / "Unrelated.py").write_text("class Unrelated:\n    pass\n", "utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "later")

    return repo, base_ref


def test_localization_uses_base_ref_not_working_tree(
    repo_with_history: tuple[Path, str],
) -> None:
    repo, base_ref = repo_with_history
    log_lines: list[str] = []

    result = _localize_at_base_ref(
        repo_path=repo,
        base_ref=base_ref,
        localizer=RepositoryIssueLocalizer(enable_graph_memory=False),
        issue_text="`WidgetRegistry` lookup is broken",
        candidate_paths=None,
        log_lines=log_lines,
    )

    assert result.selected_files == ["src/WidgetRegistry.py"]
    assert any(base_ref in line for line in log_lines)


def test_localization_falls_back_to_working_tree_on_bad_base_ref(
    repo_with_history: tuple[Path, str],
) -> None:
    repo, _ = repo_with_history
    log_lines: list[str] = []

    result = _localize_at_base_ref(
        repo_path=repo,
        base_ref="does-not-exist",
        localizer=RepositoryIssueLocalizer(enable_graph_memory=False),
        issue_text="`Unrelated` lookup is broken",
        candidate_paths=None,
        log_lines=log_lines,
    )

    assert result.selected_files == ["src/Unrelated.py"]
    assert any("falling back to the working tree" in line for line in log_lines)


def test_localization_leaves_no_worktree_behind(
    repo_with_history: tuple[Path, str],
) -> None:
    repo, base_ref = repo_with_history

    _localize_at_base_ref(
        repo_path=repo,
        base_ref=base_ref,
        localizer=RepositoryIssueLocalizer(enable_graph_memory=False),
        issue_text="`WidgetRegistry` lookup is broken",
        candidate_paths=None,
        log_lines=[],
    )

    assert "issue-mcp-localize-" not in _git(repo, "worktree", "list")
