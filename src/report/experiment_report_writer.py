from __future__ import annotations

import csv
from pathlib import Path
from typing import Any


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _format_value(value: Any) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.6f}"
    return str(value)


def _extract_verdict(judgement: Any) -> str:
    if isinstance(judgement, dict):
        return str(judgement.get("overall_verdict", "n/a"))
    return "n/a"


def _semantic_similarity_score(value: Any) -> Any:
    if isinstance(value, dict):
        return value.get("f1")
    return value


def metrics_rows(report: dict[str, Any]) -> list[dict[str, Any]]:
    original = report["metrics"]["original"]
    modified = report["metrics"]["modified"]
    delta = report["metrics"]["delta"]
    solid = ((report.get("metrics") or {}).get("design_quality") or {}).get("solid_violation_delta")

    req_original = _to_float(
        original["intent_adherence"]["requirements_coverage"].get("coverage")
    )
    req_modified = _to_float(
        modified["intent_adherence"]["requirements_coverage"].get("coverage")
    )

    rows: list[dict[str, Any]] = []

    if isinstance(solid, dict):
        rows.append(
            {
                "dimension": "Qualidade de design",
                "metric": "Delta de violacoes SOLID",
                "original": solid.get("violations_before"),
                "modified": solid.get("violations_after"),
                "delta": solid.get("delta"),
                "unit": "ratio",
            }
        )

    rows.extend([
        {
            "dimension": "Complexidade",
            "metric": "Cognitive Complexity",
            "original": original["complexity"]["cognitive_complexity"],
            "modified": modified["complexity"]["cognitive_complexity"],
            "delta": delta["cognitive_complexity"],
            "unit": "score",
        },
        {
            "dimension": "Complexidade",
            "metric": "Complexidade Ciclomatica",
            "original": original["complexity"]["cyclomatic_complexity"],
            "modified": modified["complexity"]["cyclomatic_complexity"],
            "delta": delta["cyclomatic_complexity"],
            "unit": "score",
        },
        {
            "dimension": "Aderencia a intencao",
            "metric": "Similaridade semantica (CodeBERT)",
            "original": _semantic_similarity_score(
                original["intent_adherence"].get("semantic_similarity_codebert")
            ),
            "modified": _semantic_similarity_score(
                modified["intent_adherence"].get("semantic_similarity_codebert")
            ),
            "delta": None,
            "unit": "n/a",
        },
        {
            "dimension": "Aderencia a intencao",
            "metric": "Cobertura dos requisitos",
            "original": req_original,
            "modified": req_modified,
            "delta": req_modified - req_original,
            "unit": "ratio",
        },
        {
            "dimension": "Aderencia a intencao",
            "metric": "Taxa de testes aprovados",
            "original": _to_float(original["intent_adherence"]["test_pass_rate"].get("rate")),
            "modified": _to_float(modified["intent_adherence"]["test_pass_rate"].get("rate")),
            "delta": _to_float(modified["intent_adherence"]["test_pass_rate"].get("rate"))
            - _to_float(original["intent_adherence"]["test_pass_rate"].get("rate")),
            "unit": "ratio",
        },
        {
            "dimension": "Legibilidade",
            "metric": "Buse-Weimer (proxy)",
            "original": original["readability"].get("buse_weimer_proxy"),
            "modified": modified["readability"].get("buse_weimer_proxy"),
            "delta": delta["buse_weimer_proxy"],
            "unit": "ratio",
        },
        {
            "dimension": "Legibilidade",
            "metric": "Avaliacao por LLM",
            "original": (original["readability"].get("llm_evaluation") or {}).get("score"),
            "modified": (modified["readability"].get("llm_evaluation") or {}).get("score"),
            "delta": None,
            "unit": "ratio",
        },
    ])

    return rows


def write_csv_report(csv_path: Path, rows: list[dict[str, Any]]) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["dimension", "metric", "original", "modified", "delta", "unit"],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_log_report(log_path: Path, log_lines: list[str]) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("\n".join(log_lines) + "\n", encoding="utf-8")


def write_markdown_report(
    markdown_path: Path,
    report: dict[str, Any],
    rows: list[dict[str, Any]],
    json_path: Path,
    csv_path: Path,
    log_path: Path,
) -> None:
    verdict = _extract_verdict(report["mcp"].get("judgement"))
    run_config = report.get("run_config", {})
    llm_cfg = run_config.get("llm", {})
    mcp_cfg = run_config.get("mcp_server", {})
    metrics_cfg = run_config.get("metrics", {})
    github_cfg = run_config.get("github", {})

    lines: list[str] = []
    lines.append("# Relatorio de Execucao do Experimento")
    lines.append("")
    lines.append("## Resumo")
    lines.append("")
    lines.append(f"- Issue: {report['issue']['url']}")
    lines.append(f"- Titulo: {report['issue']['title']}")
    lines.append(f"- Repositorio alvo: {report['subject']['repo_path']}")
    target_files = report["subject"].get("target_files") or []
    if target_files:
        lines.append(f"- Arquivos avaliados: {len(target_files)}")
        for file_path in target_files:
            lines.append(f"  - {file_path}")
    else:
        lines.append(f"- Arquivo avaliado: {report['subject'].get('target_file', 'n/a')}")
    lines.append(f"- Base ref: {report['subject']['base_ref']}")
    lines.append(f"- Head ref: {report['subject']['head_ref']}")
    lines.append(f"- Verdict MCP: {verdict}")
    lines.append("")
    localizer = report["subject"].get("localizer") or {}
    if localizer:
        lines.append("## Localizer")
        lines.append("")
        lines.append(f"- Strategies loaded: {localizer.get('strategy_count', 'n/a')}")
        details = localizer.get("details") or []
        if details:
            lines.append("- Top localized candidates:")
            for item in details[:5]:
                if not isinstance(item, dict):
                    continue
                lines.append(
                    f"  - {item.get('path', 'n/a')} (score={item.get('score', 'n/a')})"
                )
        lines.append("")

    lines.append("## Configuracoes da Execucao")
    lines.append("")
    lines.append(f"- GitHub API base: {github_cfg.get('api_base', 'n/a')}")
    lines.append(f"- GitHub autenticado: {github_cfg.get('authenticated', 'n/a')}")
    lines.append(f"- PR detectado automaticamente: {github_cfg.get('detected_pr', 'n/a')}")
    lines.append(f"- LLM model: {llm_cfg.get('model', 'n/a')}")
    lines.append(f"- LLM endpoint: {llm_cfg.get('endpoint', 'n/a')}")
    lines.append(f"- LLM temperature: {llm_cfg.get('temperature', 'n/a')}")
    lines.append(f"- LLM seed: {llm_cfg.get('seed', 'n/a')}")
    lines.append(f"- LLM notes: {llm_cfg.get('notes', 'n/a')}")
    lines.append(f"- MCP command: {mcp_cfg.get('command', 'n/a')}")
    lines.append(f"- MCP args: {mcp_cfg.get('args', 'n/a')}")
    lines.append(f"- Metrics semantic scorer: {metrics_cfg.get('semantic_similarity_model', 'n/a')}")
    lines.append("")
    lines.append("## Artefatos")
    lines.append("")
    lines.append(f"- JSON detalhado: {json_path}")
    lines.append(f"- CSV de metricas: {csv_path}")
    lines.append(f"- Log de execucao: {log_path}")
    lines.append("")
    lines.append("## Logs e Ferramentas MCP")
    lines.append("")
    tool_names = report["mcp"].get("tool_names", [])
    lines.append(f"- Ferramentas registradas: {', '.join(tool_names) if tool_names else 'n/a'}")
    lines.append(f"- Build status: {report['testability_gate']['build_status']}")
    lines.append(f"- Test status: {report['testability_gate']['test_status']}")
    lines.append(f"- Justificativa gate: {report['testability_gate']['reason']}")
    lines.append("")
    lines.append("## Tabela Final de Metricas")
    lines.append("")
    lines.append("| Dimensao | Metrica | Original | Modificado | Delta | Unidade |")
    lines.append("|---|---|---:|---:|---:|---|")
    for row in rows:
        lines.append(
            "| "
            f"{row['dimension']} | {row['metric']} | {_format_value(row['original'])} | "
            f"{_format_value(row['modified'])} | {_format_value(row['delta'])} | {row['unit']} |"
        )
    lines.append("")

    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
