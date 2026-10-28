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
            "candidate_paths": ["src/a.py", "src/b.py", "src/c.py"],
            "candidate_source": "explicit_candidate_paths",
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


def test_report_preserves_atomic_patch_and_focused_compile_metadata(tmp_path: Path):
    report = _base_report()
    report["mcp"]["build_repair"] = [
        {
            "attempt": 1,
            "repair_mode": "scoped_patch",
            "group_id": "group-A",
            "source_sha256": "source-hash",
            "repaired_files": ["src/a.py"],
            "patch_summary": {"edit_count": 1},
            "focused_verification": {"status": "pass", "focus_files": ["src/a.py"]},
            "candidate_accepted": True,
            "decision_reason": "Build passed.",
        }
    ]
    output = tmp_path / "report.md"
    write_markdown_report(
        output,
        report,
        metrics_rows(report),
        tmp_path / "report.json",
        tmp_path / "report.csv",
        tmp_path / "report.log",
    )
    text = output.read_text(encoding="utf-8")
    assert "group-A" in text and "source-hash" in text
    assert "Compilacao focada: pass" in text


def test_metrics_rows_includes_solid_and_semantic_metrics() -> None:
    rows = metrics_rows(_base_report())
    metrics = {row["metric"] for row in rows}
    assert "Delta de violacoes SOLID" in metrics
    assert "Similaridade semantica (CodeBERT)" in metrics


def test_report_preserves_issue_evidence_discovery_and_ownership(tmp_path: Path):
    report = _base_report()
    report["issue"]["discussion"] = {
        "fingerprint": "abc123",
        "cutoff": None,
        "fetched_comments": 8,
        "omitted_comments": 3,
        "omitted_blocks": 1,
        "notes": ["No historical cutoff was supplied."],
        "evidence": [
            {
                "source_id": "comment:99",
                "url": "https://example/comment/99",
                "author": "reviewer",
                "updated_at": "2026-01-01",
            }
        ],
    }
    report["mcp"]["plan"] = {
        "nfr_discovery_source": "issue_evidence",
        "nfr_focus": ["Reliability", "Maintainability"],
        "nfr_discovery": [
            {
                "nfr_id": "NFR-R",
                "evidence_ids": ["comment:99"],
                "rationale": "Counting must be correct.",
            }
        ],
        "issue_summary": {
            "requirements": [
                {
                    "requirement_id": "R1",
                    "text": "Increment once.",
                    "evidence_ids": ["comment:99"],
                    "acceptance_check": "Count equals one.",
                }
            ],
            "unresolved_questions": [],
        },
        "implementation_plan": [
            {
                "step_id": "S1",
                "target_file": "Counter.cs",
                "symbol": "Increment",
                "action": "modify",
                "start_line": 4,
                "end_line": 4,
                "requirement_ids": ["R1"],
                "depends_on": [],
                "validation": ["Run counting test."],
            }
        ],
    }
    output = tmp_path / "report.md"
    write_markdown_report(
        output,
        report,
        metrics_rows(report),
        tmp_path / "report.json",
        tmp_path / "report.csv",
        tmp_path / "report.log",
    )
    text = output.read_text(encoding="utf-8")
    for expected in [
        "abc123",
        "issue_evidence",
        "comment:99",
        "reviewer",
        "NFR-R",
        "Maintainability",
        "R1",
        "Count equals one.",
        "Counter.cs::Increment",
        "Run counting test.",
        "No historical cutoff",
    ]:
        assert expected in text


def test_report_preserves_stage_results_and_candidate_rejection(tmp_path: Path):
    report = _base_report()
    report["run_config"]["auto_repair"] = {
        "strategy": "multi_branch",
        "search_width": 2,
        "concurrency": 3,
        "max_depth": 3,
        "max_branch_seconds": 300,
    }
    report["verification"] = {
        "build": {
            "stages": [
                {
                    "stage": "prerequisite",
                    "status": "pass",
                    "duration_seconds": 1.25,
                    "command": ["make", "generate"],
                }
            ]
        }
    }
    report["mcp"]["build_repair"] = [
        {
            "attempt": 1,
            "candidate_accepted": False,
            "decision_reason": "No diagnostic progress",
            "introduced_diagnostics": [],
            "resolved_diagnostics": [],
            "stopped_reason": "Repeated errors",
            "branch_id": "checkpoint-1",
            "branch_depth": 2,
            "branch_state": "rolled_back",
            "branch_reason": "Provisional branch depth budget exhausted.",
            "transaction_accepted": False,
            "handoff_from": "Models.cs",
            "handoff_to": "Generator.cs",
            "local_resolved_diagnostics": [["Models.cs", "E1", "Missing"]],
            "local_introduced_diagnostics": [],
            "local_decision_reason": "Local progress",
        }
    ]
    path = tmp_path / "report.md"
    write_markdown_report(
        path,
        report,
        metrics_rows(report),
        tmp_path / "r.json",
        tmp_path / "r.csv",
        tmp_path / "r.log",
    )
    content = path.read_text(encoding="utf-8")
    assert (
        "Estrategia de auto-reparo: multi_branch; largura=2; concorrencia=3; profundidade=3"
        in content
    )
    assert "Transferencia de owner: `Models.cs` -> `Generator.cs`" in content
    assert "Progresso local: novos=0; resolvidos=1; decisao=Local progress" in content
    assert "Branch: `checkpoint-1`; profundidade=2; estado=rolled_back" in content
    assert "Provisional branch depth budget exhausted." in content
    assert "Etapa de build prerequisite: status=pass" in content
    assert "comando=`make generate`" in content
    assert "Candidato aceito: False" in content
    assert "No diagnostic progress" in content
    assert "Motivo da parada: Repeated errors" in content


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
    assert "Arquivos-alvo selecionados pelo localizador: 2" in md
    assert "Universo de candidatos: explicit_candidate_paths" in md
    assert "Candidatos fornecidos ao localizador: 3" in md
    assert "Evidência dos arquivos-alvo:" in md


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
    assert "Arquivos-alvo selecionados pelo localizador: 0" in content
