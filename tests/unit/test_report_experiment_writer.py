from __future__ import annotations

from pathlib import Path

from src.report.experiment_report_writer import (
    _extract_verdict,
    _format_value,
    _to_float,
    metrics_rows,
    write_csv_report,
    write_log_report,
    write_markdown_report,
)


def _base_report() -> dict:
    return {
        "issue": {"url": "https://example/1", "title": "Issue title"},
        "subject": {
            "repo_path": "repo",
            "target_files": ["src/a.py", "src/b.py"],
            "base_ref": "main",
            "head_ref": "feature",
            "localizer": {
                "strategy_count": 2,
                "details": [{"path": "src/a.py", "score": 1.0}],
            },
        },
        "run_config": {
            "github": {
                "api_base": "https://api.github.com",
                "authenticated": True,
                "detected_pr": 10,
            },
            "llm": {
                "model": "m",
                "endpoint": "e",
                "temperature": 0.1,
                "seed": 42,
                "notes": "n",
            },
            "mcp_server": {"command": "python", "args": ["-m", "src.main"]},
            "metrics": {"semantic_similarity_model": "codebert"},
        },
        "mcp": {
            "tool_names": ["a", "b"],
            "judgement": {"overall_verdict": "acceptable"},
        },
        "testability_gate": {
            "build_status": "pass",
            "test_status": "pass",
            "reason": "ok",
        },
        "metrics": {
            "design_quality": {
                "solid_violation_delta": {
                    "violations_before": 5,
                    "violations_after": 2,
                    "delta": 0.6,
                }
            },
            "original": {
                "complexity": {"cognitive_complexity": 4, "cyclomatic_complexity": 3},
                "intent_adherence": {
                    "requirements_coverage": {"coverage": 0.5},
                    "semantic_similarity_codebert": {"f1": 0.7},
                    "test_pass_rate": {"rate": 0.8},
                },
                "readability": {
                    "buse_weimer_proxy": 0.4,
                    "llm_evaluation": {"score": 0.6},
                },
            },
            "modified": {
                "complexity": {"cognitive_complexity": 3, "cyclomatic_complexity": 2},
                "intent_adherence": {
                    "requirements_coverage": {"coverage": 0.9},
                    "semantic_similarity_codebert": {"f1": 0.8},
                    "test_pass_rate": {"rate": 0.95},
                },
                "readability": {
                    "buse_weimer_proxy": 0.7,
                    "llm_evaluation": {"score": 0.75},
                },
            },
            "delta": {
                "cognitive_complexity": -1,
                "cyclomatic_complexity": -1,
                "buse_weimer_proxy": 0.3,
            },
        },
    }


def test_scalar_helpers_cover_fallbacks() -> None:
    assert _to_float("1.5") == 1.5
    assert _to_float("bad", default=9.0) == 9.0
    assert _format_value(None) == "n/a"
    assert _format_value(1.23456789) == "1.234568"
    assert _extract_verdict({"overall_verdict": "acceptable"}) == "acceptable"
    assert _extract_verdict("not-a-dict") == "n/a"


def test_metrics_rows_includes_solid_and_semantic_metrics() -> None:
    rows = metrics_rows(_base_report())
    metrics = {row["metric"] for row in rows}
    assert "Delta de violacoes SOLID" in metrics
    assert "Similaridade semantica (CodeBERT)" in metrics


def test_write_reports_generate_expected_files(tmp_path: Path) -> None:
    report = _base_report()
    rows = metrics_rows(report)

    csv_path = tmp_path / "out" / "report.csv"
    log_path = tmp_path / "out" / "run.log"
    md_path = tmp_path / "out" / "summary.md"
    json_path = tmp_path / "out" / "report.json"

    write_csv_report(csv_path, rows)
    write_log_report(log_path, ["line1", "line2"])
    write_markdown_report(md_path, report, rows, json_path, csv_path, log_path)

    assert csv_path.exists()
    assert log_path.exists()
    assert md_path.exists()

    md = md_path.read_text(encoding="utf-8")
    assert "Relatorio de Execucao do Experimento" in md
    assert "Verdict MCP: acceptable" in md
    assert "src/a.py" in md


def test_write_markdown_report_handles_missing_target_files_branch(
    tmp_path: Path,
) -> None:
    report = _base_report()
    report["subject"].pop("target_files", None)
    report["subject"]["target_file"] = "single.py"

    rows = metrics_rows(report)
    md_path = tmp_path / "summary.md"
    write_markdown_report(
        md_path,
        report,
        rows,
        tmp_path / "r.json",
        tmp_path / "r.csv",
        tmp_path / "r.log",
    )

    content = md_path.read_text(encoding="utf-8")
    assert "Arquivo avaliado: single.py" in content
