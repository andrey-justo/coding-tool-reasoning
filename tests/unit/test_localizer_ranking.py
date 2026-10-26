from __future__ import annotations

from pathlib import Path

import pytest

from src.models.localizer.models import LocalizationHit
from src.service.localizer.discovery import discover_repository_code_files
from src.service.localizer.orchestrator import RepositoryIssueLocalizer
from src.service.localizer.strategies.tfidf_content import TfIdfContentStrategy
from src.service.localizer.utils import (
    extract_focus_symbols,
    extract_symbols,
    extract_weighted_symbols,
)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_weighted_symbols_rank_code_shaped_identifiers_first() -> None:
    issue = (
        "The generator fails for collection fields.\n"
        "A `List<Reading>` field reports AKKASG003 when AkkaSerializable is used.\n"
    )

    ranked = extract_symbols(issue)

    assert ranked.index("AKKASG003") < ranked.index("generator")
    assert ranked.index("AkkaSerializable") < ranked.index("generator")


def test_weighted_symbols_drop_language_keywords() -> None:
    issue = "```csharp\npublic sealed record SensorBatch(string DeviceId);\n```"

    symbols = {symbol.lower() for symbol, _ in extract_weighted_symbols(issue)}

    assert "sensorbatch" in symbols
    assert "deviceid" in symbols
    assert "public" not in symbols
    assert "sealed" not in symbols
    assert "record" not in symbols
    assert "string" not in symbols


def test_focus_symbols_keep_only_code_shaped_identifiers() -> None:
    issue = (
        "Serialization breaks when `AkkaSerializerFormatter` rejects generic targets."
    )

    focus = extract_focus_symbols(issue)

    assert "AkkaSerializerFormatter" in focus
    assert "rejects" not in focus


def test_focus_symbols_fall_back_to_prose_when_no_code_identifiers() -> None:
    issue = "retry request fails intermittently"

    focus = extract_focus_symbols(issue)

    assert focus
    assert "retry" in focus


def test_tfidf_strategy_ignores_symbols_present_in_most_files(tmp_path: Path) -> None:
    # "Serializer" appears everywhere and therefore discriminates nothing, while
    # "AKKASG003" appears in a single file.
    for index in range(10):
        _write(tmp_path / f"file_{index}.cs", "class Serializer { }")
    _write(tmp_path / "target.cs", "class Serializer { /* AKKASG003 */ }")

    strategy = TfIdfContentStrategy(max_document_frequency_ratio=0.2)
    hits = strategy.score(
        repo_path=tmp_path,
        issue_text="`Serializer` fails with AKKASG003",
        candidate_paths=[f"file_{i}.cs" for i in range(10)] + ["target.cs"],
    )

    assert set(hits) == {"target.cs"}
    assert "AKKASG003" in hits["target.cs"].reasons[0]


def test_tfidf_strategy_does_not_reward_file_length(tmp_path: Path) -> None:
    _write(tmp_path / "precise.cs", "class A { void Build(WidgetRegistry r) {} }")
    _write(
        tmp_path / "verbose.cs",
        "class B {\n" + ("    // WidgetRegistry mentioned again\n" * 400) + "}",
    )
    for index in range(30):
        _write(tmp_path / f"filler_{index}.cs", "class Filler { }")

    candidates = ["precise.cs", "verbose.cs"] + [f"filler_{i}.cs" for i in range(30)]
    strategy = TfIdfContentStrategy()
    hits = strategy.score(
        repo_path=tmp_path,
        issue_text="`WidgetRegistry` lookup is broken",
        candidate_paths=candidates,
    )

    # The verbose file still ranks first, but saturation caps the advantage at
    # the 3x ceiling instead of the 400x ratio of raw occurrences.
    assert hits["verbose.cs"].score <= 3 * hits["precise.cs"].score


def test_discovery_includes_dotnet_project_files(tmp_path: Path) -> None:
    _write(tmp_path / "src" / "App" / "App.csproj", "<Project />")
    _write(tmp_path / "src" / "App" / "Program.cs", "class Program { }")

    found = discover_repository_code_files(tmp_path)

    assert "src/App/App.csproj" in found
    assert "src/App/Program.cs" in found


class _StubStrategy:
    def __init__(self, name: str, scores: dict[str, float]) -> None:
        self.name = name
        self._scores = scores

    def score(self, repo_path, issue_text, candidate_paths):  # noqa: ANN001
        return {
            path: LocalizationHit(path=path, score=value, reasons=[self.name])
            for path, value in self._scores.items()
        }


def test_localizer_normalizes_strategy_scales_before_aggregating(
    tmp_path: Path,
) -> None:
    # The loud strategy emits scores two orders of magnitude larger, but points
    # at the wrong file. Without normalization it would decide the ranking.
    loud = _StubStrategy("regex", {"wrong.py": 900.0, "right.py": 100.0})
    precise = _StubStrategy("tfidf", {"right.py": 5.0, "wrong.py": 0.5})

    localizer = RepositoryIssueLocalizer(strategies=[loud, precise])
    result = localizer.localize(
        repo_path=tmp_path,
        issue_text="anything",
        candidate_paths=["wrong.py", "right.py"],
    )

    assert result.selected_files == ["right.py"]


def test_localizer_preserves_all_positive_ranked_files(tmp_path: Path) -> None:
    scores = {f"file_{index}.py": 1.0 for index in range(20)}
    scores["best.py"] = 2.0
    scores["below_threshold.py"] = 0.99
    strategy = _StubStrategy(
        "tfidf",
        scores,
    )
    candidates = list(scores)

    result = RepositoryIssueLocalizer(strategies=[strategy]).localize(
        repo_path=tmp_path,
        issue_text="anything",
        candidate_paths=candidates,
    )

    assert len(result.selected_files) == 21
    assert result.selected_files[0] == "best.py"
    assert "below_threshold.py" not in result.selected_files
    assert len(result.details) == len(candidates)


def test_localizer_rejects_invalid_relative_threshold() -> None:
    for threshold in (0.0, -0.1, 1.1):
        with pytest.raises(ValueError, match="min_relative_score"):
            RepositoryIssueLocalizer(min_relative_score=threshold)
