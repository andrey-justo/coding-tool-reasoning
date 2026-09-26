from __future__ import annotations

import json
from pathlib import Path

from src.evaluation.metrics.solid import SolidMetricsStrategy
import src.mcp.swe_mcp_server as swe_mcp_server
from src.mcp.swe_mcp_server import SweMcpServerContextProvider
from src.models.swe_config import SweMcpConfig
from src.service.localizer import models as models_module
from src.service.localizer.ast import symbol_set as symbol_set_module
from src.service import language_detection


def test_language_detection_from_file_paths_and_text_markers() -> None:
    assert language_detection.infer_language_from_file_paths(None) is None
    assert language_detection.infer_language_from_file_paths([]) is None
    assert (
        language_detection.infer_language_from_file_paths(
            ["src/app.ts", "src/main.tsx", "README.md"]
        )
        == "typescript"
    )
    assert (
        language_detection.infer_language_from_file_paths(["README.md", "notes.txt"])
        is None
    )

    assert (
        language_detection.infer_language_from_text("Refactor this Python service using pytest")
        == "python"
    )
    assert (
        language_detection.infer_language_from_text("Build with maven and junit for java app")
        == "java"
    )
    assert (
        language_detection.infer_language_from_text(
            "Completely unrelated prose without framework markers"
        )
        is None
    )


def test_solid_metrics_strategy_delta_count_and_compute() -> None:
    strategy = SolidMetricsStrategy()

    improved = strategy.solid_violation_delta(violations_before=10, violations_after=4)
    assert improved.delta == 0.6
    assert improved.absolute_delta == -6

    unchanged_zero = strategy.solid_violation_delta(violations_before=0, violations_after=0)
    assert unchanged_zero.delta == 0.0

    regressed_from_zero = strategy.solid_violation_delta(
        violations_before=0,
        violations_after=2,
    )
    assert regressed_from_zero.delta == -1.0

    clamped = strategy.solid_violation_delta(violations_before=-2, violations_after=-9)
    assert clamped.violations_before == 0
    assert clamped.violations_after == 0

    issues = [
        {"rule": "solid:srp", "severity": "MAJOR"},
        {"rule": "solid:ocp", "severity": "minor"},
        {"rule": "other", "severity": "CRITICAL"},
    ]
    assert strategy.count_violations_from_issues(issues) == 3
    assert (
        strategy.count_violations_from_issues(
            issues,
            rule_keys={"solid:srp", "solid:ocp"},
        )
        == 2
    )
    assert (
        strategy.count_violations_from_issues(
            issues,
            severities={"major", "critical"},
        )
        == 2
    )

    assert strategy.compute(None, 1) is None
    assert strategy.compute(1, None) is None
    computed = strategy.compute(5, 3)
    assert computed == {
        "violations_before": 5,
        "violations_after": 3,
        "delta": 0.4,
        "absolute_delta": -2,
    }


def test_localizer_reexport_modules_are_importable() -> None:
    assert symbol_set_module.__all__ == ["SymbolSet"]
    assert "LocalizationHit" in models_module.__all__
    assert "LocalizerResult" in models_module.__all__
    assert "LocalizationStrategy" in models_module.__all__


def test_swe_mcp_server_helpers_and_wrappers(monkeypatch, tmp_path: Path) -> None:
    provider = SweMcpServerContextProvider(repo_root=str(tmp_path))

    assert provider._safe_read_text(str(tmp_path / "missing.txt")) == ""

    test_file = tmp_path / "sample.txt"
    test_file.write_text("  hello  \n", encoding="utf-8")
    assert provider._safe_read_text(str(test_file)) == "hello"

    invalid_json = tmp_path / "invalid.json"
    invalid_json.write_text("{not-json", encoding="utf-8")
    assert provider._load_json_payload(str(invalid_json)) == {}

    list_json = tmp_path / "list.json"
    list_json.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
    assert provider._load_json_payload(str(list_json)) == {}

    valid_json = tmp_path / "valid.json"
    valid_json.write_text(json.dumps({"name": "retry policy"}), encoding="utf-8")
    loaded = provider._load_json_payload(str(valid_json))
    assert loaded == {"name": "retry policy"}

    assert provider._find_first_file_with_stem(str(tmp_path / "no-dir"), "x") is None

    examples_dir = tmp_path / "tests" / "examples"
    examples_dir.mkdir(parents=True)
    (examples_dir / "retry_pattern.py").write_text("def retry():\n    return 1\n", encoding="utf-8")

    assert provider._resolve_code_example("retry_pattern")
    assert provider._extract_unit_test_example({"unit_test_example": "assert True"}) == "assert True"
    assert provider._extract_unit_test_example({"tests": ["a", "", "b"]}) == "- a\n- b"

    data_path = tmp_path / "payload.json"
    data_path.write_text(json.dumps({"name": "retry_pattern"}), encoding="utf-8")
    payload = provider._build_concern_data_payload("retry_pattern", str(data_path))
    assert payload["EXAMPLE_DESCRIPTION"] == "Retry Pattern example"
    assert payload["DESIGN_PATTERN_NAME"] == "retry_pattern"
    assert "def retry()" in payload["CODE_EXAMPLE"]

    class _FakeProvider:
        def __init__(self) -> None:
            self.context_calls = 0
            self.register_calls = 0

        def create_swe_server_context(self, force_reload: bool = False):
            self.context_calls += 1
            return {"force_reload": force_reload}

        def register_swe_tools_on_mcp(self, mcp):
            self.register_calls += 1
            mcp["registered"] = True

    fake_provider = _FakeProvider()
    monkeypatch.setattr(swe_mcp_server, "_DEFAULT_CONTEXT_PROVIDER", fake_provider)

    wrapped_context = swe_mcp_server.create_swe_server_context(force_reload=True)
    assert wrapped_context == {"force_reload": True}

    container: dict[str, bool] = {}
    swe_mcp_server.register_swe_tools_on_mcp(container)
    assert container["registered"] is True
    assert fake_provider.context_calls == 1
    assert fake_provider.register_calls == 1


def test_swe_mcp_server_load_concern_assets_with_subject_filter(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir(parents=True)

    templates_root = repo_root / "knowledge" / "template"
    templates_root.mkdir(parents=True)
    (templates_root / "base.md").write_text("template body", encoding="utf-8")

    data_group_a = repo_root / "knowledge" / "data" / "reliability" / "group_a"
    data_group_b = repo_root / "knowledge" / "data" / "reliability" / "group_b"
    data_group_a.mkdir(parents=True)
    data_group_b.mkdir(parents=True)
    (data_group_a / "data.json").write_text(json.dumps({"name": "group_a"}), encoding="utf-8")
    (data_group_b / "data.json").write_text(json.dumps({"name": "group_b"}), encoding="utf-8")

    config = SweMcpConfig()
    config.concern_assets.swe_concern = "reliability"
    config.concern_assets.swe_subject = "group_a"

    provider = SweMcpServerContextProvider(repo_root=str(repo_root))
    assets = provider._load_concern_assets(config=config)

    template_assets = [asset for asset in assets if asset["kind"] == "swe_concern_template"]
    data_assets = [asset for asset in assets if asset["kind"] == "swe_concern_data"]
    assert len(template_assets) == 1
    assert len(data_assets) == 1
    assert data_assets[0]["concern_group"] == "group_a"
