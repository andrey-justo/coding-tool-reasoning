from __future__ import annotations

import argparse
import asyncio
import difflib
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from src.evaluation.experiment_metrics import ExperimentMetricsEvaluator
from src.evaluation.sonarqube_client import SonarIssueQuery, SonarQubeClient
from src.models.swe_config import SweMcpConfig
from src.report.experiment_report_writer import (
    metrics_rows,
    write_csv_report,
    write_log_report,
    write_markdown_report,
)
from src.service.localizer import RepositoryIssueLocalizer


@dataclass(frozen=True)
class ParsedIssueUrl:
    owner: str
    repo: str
    issue_number: int
    url: str


def _default_execution_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _render_with_execution_id(value: str | None, execution_id: str) -> str | None:
    if value is None:
        return None
    try:
        return value.format(execution_id=execution_id)
    except Exception:
        return value


def _run_git(repo_path: Path, args: list[str]) -> str:
    return subprocess.check_output(
        ["git", "-C", str(repo_path), *args], text=True
    ).strip()


def _coerce_json(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def _extract_code_blocks(markdown_text: str | None) -> list[dict[str, str]]:
    if not markdown_text:
        return []
    pattern = re.compile(r"```([a-zA-Z0-9_+-]*)\n(.*?)```", re.DOTALL)
    blocks: list[dict[str, str]] = []
    for match in pattern.finditer(markdown_text):
        language = (match.group(1) or "text").strip() or "text"
        code = (match.group(2) or "").strip()
        if code:
            blocks.append({"language": language, "code": code})
    return blocks


def _as_pretty_json(value: Any) -> str:
    try:
        return json.dumps(value, indent=2, ensure_ascii=False)
    except TypeError:
        return str(value)


def _write_llm_debug_artifacts(
    debug_dir: Path,
    issue_prompt: str,
    original_code: str,
    reference_modified_code: str,
    mcp_payload: dict[str, Any],
) -> list[str]:
    debug_dir.mkdir(parents=True, exist_ok=True)
    for old_md in debug_dir.glob("*.md"):
        old_md.unlink(missing_ok=True)

    apply_value = mcp_payload.get("apply")
    apply_payload = (
        apply_value if isinstance(apply_value, dict) else {"error": str(apply_value)}
    )
    generated_code = apply_payload.get("generated_code", original_code)

    plan_payload = mcp_payload.get("plan") or {}
    judge_payload = mcp_payload.get("judgement") or {}

    debug_items: list[dict[str, Any]] = [
        {
            "prefix": "01-plan_swe_code_change",
            "call_name": "plan_swe_code_change",
            "llm_input": plan_payload.get("llm_prompt")
            or _as_pretty_json(
                {
                    "problem_description": issue_prompt,
                    "nfr_focus": plan_payload.get("nfr_focus"),
                }
            ),
            "llm_output": plan_payload.get("llm_raw_response"),
            "parsed_output": plan_payload,
        },
        {
            "prefix": "02-build_swe_code_context",
            "call_name": "build_swe_code_context",
            "llm_input": (
                "No direct LLM call in this step.\n\n"
                "Context is assembled from SWE knowledge base + templates based on the plan."
            ),
            "llm_output": None,
            "parsed_output": mcp_payload.get("context"),
        },
        {
            "prefix": "03-apply_plan_swe_code_change",
            "call_name": "apply_plan_swe_code_change",
            "llm_input": apply_payload.get("prompt")
            or "Prompt not captured for apply_plan_swe_code_change.",
            "llm_output": apply_payload.get("raw_response"),
            "parsed_output": mcp_payload.get("apply"),
        },
        {
            "prefix": "04-judge_swe_code_change",
            "call_name": "judge_swe_code_change",
            "llm_input": judge_payload.get("llm_prompt")
            or "Prompt not captured for judge_swe_code_change.",
            "llm_output": judge_payload.get("llm_raw_response"),
            "parsed_output": judge_payload,
        },
    ]

    written_files: list[str] = []
    for item in debug_items:
        llm_input = str(item.get("llm_input") or "")
        llm_output = item.get("llm_output")
        parsed_output = item.get("parsed_output")
        extracted_blocks = _extract_code_blocks(
            llm_output if isinstance(llm_output, str) else None
        )

        input_lines: list[str] = []
        input_lines.append(f"# LLM Input Prompt: {item['call_name']}")
        input_lines.append("")
        input_lines.append("```text")
        input_lines.append(llm_input)
        input_lines.append("```")

        output_lines: list[str] = []
        output_lines.append(f"# LLM Output: {item['call_name']}")
        output_lines.append("")
        if llm_output:
            output_lines.append("```text")
            output_lines.append(str(llm_output))
            output_lines.append("```")
        else:
            output_lines.append("No raw LLM response captured for this step.")
        output_lines.append("")
        output_lines.append("## Parsed Output Snapshot")
        output_lines.append("")
        output_lines.append("```json")
        output_lines.append(_as_pretty_json(parsed_output))
        output_lines.append("```")
        output_lines.append("")
        output_lines.append("## Extracted Code Blocks")
        output_lines.append("")
        if extracted_blocks:
            for idx, block in enumerate(extracted_blocks, start=1):
                output_lines.append(f"### Block {idx} ({block['language']})")
                output_lines.append("")
                output_lines.append(f"```{block['language']}")
                output_lines.append(block["code"])
                output_lines.append("```")
                output_lines.append("")
        else:
            output_lines.append("No fenced code blocks were found in the LLM output.")

        input_file = debug_dir / f"{item['prefix']}-input.md"
        output_file = debug_dir / f"{item['prefix']}-output.md"
        input_file.write_text("\n".join(input_lines) + "\n", encoding="utf-8")
        output_file.write_text("\n".join(output_lines) + "\n", encoding="utf-8")
        written_files.append(str(input_file))
        written_files.append(str(output_file))

    # Keep convenience side-by-side snapshots for quick diff-oriented inspection.
    compare_file = debug_dir / "05-original_vs_generated_code.md"
    compare_file.write_text(
        "\n".join(
            [
                "# Original Vs Generated Code",
                "",
                "## Original Code",
                "",
                "```",
                original_code,
                "```",
                "",
                "## Reference Modified Code",
                "",
                "```",
                reference_modified_code,
                "```",
                "",
                "## Generated Code",
                "",
                "```",
                str(
                    generated_code if isinstance(generated_code, str) else original_code
                ),
                "```",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    written_files.append(str(compare_file))

    diff_file = debug_dir / "06-generated_code_diff.md"
    diff_file.write_text(
        "\n".join(
            [
                "# Generated Code Unified Diff",
                "",
                "```diff",
                "\n".join(
                    difflib.unified_diff(
                        original_code.splitlines(),
                        str(
                            generated_code
                            if isinstance(generated_code, str)
                            else original_code
                        ).splitlines(),
                        fromfile="original",
                        tofile="generated",
                        lineterm="",
                    )
                ),
                "```",
                "",
                "## Apply Metadata",
                "",
                "```json",
                _as_pretty_json(
                    {
                        "used_fallback_to_original": apply_payload.get(
                            "used_fallback_to_original"
                        ),
                        "apply_error": apply_payload.get("error"),
                        "chunked": apply_payload.get("chunked"),
                        "chunk_count": apply_payload.get("chunk_count"),
                        "chunk_errors": apply_payload.get("chunk_errors"),
                    }
                ),
                "```",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    written_files.append(str(diff_file))

    return written_files


def _parse_issue_url(issue_url: str) -> ParsedIssueUrl:
    match = re.search(r"github\.com/([^/]+)/([^/]+)/issues/(\d+)", issue_url)
    if not match:
        raise ValueError(f"Unsupported issue URL format: {issue_url}")
    owner, repo, number_text = match.group(1), match.group(2), match.group(3)
    return ParsedIssueUrl(
        owner=owner, repo=repo, issue_number=int(number_text), url=issue_url
    )


class GitHubIssueClient:
    def __init__(
        self, token: str | None = None, api_base: str = "https://api.github.com"
    ) -> None:
        self._api_base = api_base.rstrip("/")
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Accept": "application/vnd.github+json",
                "User-Agent": "coding-tool-reasoning-experiment-runner",
            }
        )
        if token:
            self._session.headers["Authorization"] = f"Bearer {token}"

    @property
    def authenticated(self) -> bool:
        return "Authorization" in self._session.headers

    @property
    def api_base(self) -> str:
        return self._api_base

    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{self._api_base}{path}"
        response = self._session.get(url, params=params, timeout=30)
        response.raise_for_status()
        return response.json()

    def fetch_issue(self, owner: str, repo: str, issue_number: int) -> dict[str, Any]:
        return self._get(f"/repos/{owner}/{repo}/issues/{issue_number}")

    def fetch_issue_comments(
        self, owner: str, repo: str, issue_number: int, per_page: int = 20
    ) -> list[dict[str, Any]]:
        return self._get(
            f"/repos/{owner}/{repo}/issues/{issue_number}/comments",
            params={"per_page": per_page},
        )

    def detect_linked_pr(self, owner: str, repo: str, issue_number: int) -> int | None:
        query = f'repo:{owner}/{repo} is:pr "#{issue_number}" in:body'
        data = self._get("/search/issues", params={"q": query, "per_page": 1})
        items = data.get("items", [])
        if not items:
            return None
        return int(items[0]["number"])

    def fetch_pull(self, owner: str, repo: str, pull_number: int) -> dict[str, Any]:
        return self._get(f"/repos/{owner}/{repo}/pulls/{pull_number}")

    def fetch_pull_files(
        self, owner: str, repo: str, pull_number: int, per_page: int = 100
    ) -> list[dict[str, Any]]:
        return self._get(
            f"/repos/{owner}/{repo}/pulls/{pull_number}/files",
            params={"per_page": per_page},
        )


def _build_issue_prompt(issue: dict[str, Any], comments: list[dict[str, Any]]) -> str:
    body = issue.get("body") or ""
    lines = [
        f"Issue #{issue.get('number')}: {issue.get('title', '')}",
        "",
        "Issue body:",
        body,
        "",
    ]
    if comments:
        lines.append("Top comments:")
        for idx, comment in enumerate(comments[:5], start=1):
            user = (comment.get("user") or {}).get("login", "unknown")
            text = (comment.get("body") or "").strip()
            snippet = text[:500]
            lines.append(f"{idx}. @{user}: {snippet}")
    return "\n".join(lines)


def _resolve_head_ref(
    repo_path: Path,
    gh_client: GitHubIssueClient,
    parsed_issue: ParsedIssueUrl,
    pull_number: int | None,
    explicit_head_ref: str | None,
    log_lines: list[str],
) -> str:
    if explicit_head_ref:
        return explicit_head_ref
    if pull_number is None:
        return "HEAD"

    local_branch = f"pr-{pull_number}"
    try:
        _run_git(
            repo_path, ["fetch", "origin", f"pull/{pull_number}/head:{local_branch}"]
        )
        log_lines.append(f"Fetched PR #{pull_number} into local branch {local_branch}")
        return local_branch
    except subprocess.CalledProcessError:
        pull = gh_client.fetch_pull(parsed_issue.owner, parsed_issue.repo, pull_number)
        head_sha = ((pull.get("head") or {}).get("sha")) or ""
        if head_sha:
            try:
                _run_git(repo_path, ["fetch", "origin", head_sha])
                log_lines.append(
                    f"Could not fetch PR branch directly. Fetched PR head sha {head_sha} instead."
                )
                return head_sha
            except subprocess.CalledProcessError:
                pass
        log_lines.append("Could not fetch PR head reference; falling back to HEAD.")
        return "HEAD"


async def _run_mcp_workflow(
    repo_path: Path,
    issue_prompt: str,
    target_files: list[str],
    original_code_by_file: dict[str, str],
    nfr_focus: list[str],
    temperature: float,
    seed: int,
    log_lines: list[str],
) -> dict[str, Any]:
    workspace_root = Path(__file__).resolve().parents[2]
    server_params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "src.main", "mcp-server"],
        cwd=str(workspace_root),
        env=os.environ.copy(),
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            tool_names = [tool.name for tool in tools.tools]
            log_lines.append(f"MCP tools available: {', '.join(tool_names)}")

            plan_result = await session.call_tool(
                "plan_swe_code_change",
                {
                    "problem_description": issue_prompt,
                    "nfr_focus": nfr_focus,
                },
            )
            plan_content = _coerce_json(
                plan_result.content[0].text if plan_result.content else None
            )
            log_lines.append("plan_swe_code_change completed")

            context_result = await session.call_tool(
                "build_swe_code_context",
                {
                    "plan": plan_content,
                    "include_templates": False,
                },
            )
            context_content = _coerce_json(
                context_result.content[0].text if context_result.content else None
            )
            log_lines.append("build_swe_code_context completed")

            apply_results: dict[str, dict[str, Any]] = {}
            generated_code_by_file: dict[str, str] = {}

            for target_file in target_files:
                original_code = original_code_by_file.get(target_file, "")
                apply_result = await session.call_tool(
                    "apply_plan_swe_code_change",
                    {
                        "swe_context": context_content,
                        "original_code": original_code,
                        "target_file": target_file,
                        "temperature": temperature,
                        "seed": seed,
                    },
                )
                apply_content = _coerce_json(
                    apply_result.content[0].text if apply_result.content else None
                )
                if not isinstance(apply_content, dict):
                    apply_content = {
                        "target_file": target_file,
                        "generated_code": original_code,
                        "raw_response": "",
                        "extracted_code_blocks": [],
                        "used_fallback_to_original": True,
                        "error": str(apply_content),
                    }

                log_lines.append(
                    f"apply_plan_swe_code_change completed for {target_file}"
                )
                if apply_content.get("error"):
                    log_lines.append(
                        f"apply_plan_swe_code_change error for {target_file}: {apply_content['error']}"
                    )

                generated_code = original_code
                if isinstance(apply_content.get("generated_code"), str):
                    generated_code = str(apply_content.get("generated_code"))

                apply_results[target_file] = apply_content
                generated_code_by_file[target_file] = generated_code

            combined_original = "\n\n".join(
                f"### FILE: {path}\n{original_code_by_file.get(path, '')}"
                for path in target_files
            )
            combined_modified = "\n\n".join(
                f"### FILE: {path}\n{generated_code_by_file.get(path, '')}"
                for path in target_files
            )

            judge_result = await session.call_tool(
                "judge_swe_code_change",
                {
                    "swe_context": context_content,
                    "original_code": combined_original,
                    "modified_code": combined_modified,
                },
            )
            judge_content = _coerce_json(
                judge_result.content[0].text if judge_result.content else None
            )
            log_lines.append("judge_swe_code_change completed")

            first_target = target_files[0] if target_files else ""
            first_apply = apply_results.get(first_target, {}) if first_target else {}

            return {
                "tool_names": tool_names,
                "plan": plan_content,
                "context": context_content,
                "apply": first_apply,
                "apply_results": apply_results,
                "generated_code_by_file": generated_code_by_file,
                "judgement": judge_content,
                "combined_original_code": combined_original,
                "combined_generated_code": combined_modified,
                "server": {
                    "command": server_params.command,
                    "args": server_params.args,
                    "cwd": server_params.cwd,
                },
            }


def _run_experiment(args: argparse.Namespace) -> dict[str, Any]:
    log_lines: list[str] = []
    run_started = datetime.now(timezone.utc).isoformat()

    repo_path = Path(args.repo_path).resolve()
    parsed_issue = _parse_issue_url(args.issue_url)

    token = args.github_token or os.getenv("GITHUB_TOKEN")
    gh_client = GitHubIssueClient(token=token)

    issue = gh_client.fetch_issue(
        parsed_issue.owner, parsed_issue.repo, parsed_issue.issue_number
    )
    comments = gh_client.fetch_issue_comments(
        parsed_issue.owner,
        parsed_issue.repo,
        parsed_issue.issue_number,
        per_page=args.max_issue_comments,
    )
    detected_pr = args.pull_request_number
    if detected_pr is None and args.auto_detect_pr:
        detected_pr = gh_client.detect_linked_pr(
            parsed_issue.owner,
            parsed_issue.repo,
            parsed_issue.issue_number,
        )

    issue_prompt = _build_issue_prompt(issue, comments)

    pr_candidate_files: list[str] | None = None
    if detected_pr is not None:
        try:
            pr_files = gh_client.fetch_pull_files(
                parsed_issue.owner,
                parsed_issue.repo,
                detected_pr,
            )
            pr_candidate_files = [
                str(item.get("filename") or "").strip()
                for item in pr_files
                if str(item.get("filename") or "").strip()
            ]
            log_lines.append(
                f"Localizer candidate pool from PR #{detected_pr}: {len(pr_candidate_files)} files"
            )
        except Exception as exc:
            log_lines.append(
                f"Could not fetch PR files for localization ({type(exc).__name__}: {exc}); falling back to repository scan."
            )

    localizer_config = SweMcpConfig.load(str(repo_path)).localizer
    localizer = RepositoryIssueLocalizer(
        enable_semantic_nlp=args.enable_nlp_localizer,
        enable_graph_memory=localizer_config.enable_graph_memory,
        graph_memory_hops=localizer_config.graph_memory_hops,
    )
    localization = localizer.localize(
        repo_path=repo_path,
        issue_text=issue_prompt,
        top_k=args.max_target_files,
        candidate_paths=pr_candidate_files,
    )
    target_files = localization.selected_files
    if not target_files:
        raise ValueError("Localizer could not identify candidate files for this issue.")
    log_lines.append(
        f"Localizer selected {len(target_files)} files: {', '.join(target_files)}"
    )
    head_ref = _resolve_head_ref(
        repo_path,
        gh_client,
        parsed_issue,
        detected_pr,
        args.head_ref,
        log_lines,
    )
    base_ref = args.base_ref

    original_code_by_file: dict[str, str] = {}
    reference_modified_by_file: dict[str, str] = {}
    reference_diff_by_file: dict[str, str] = {}
    for target_file in target_files:
        original_code_by_file[target_file] = _run_git(
            repo_path, ["show", f"{base_ref}:{target_file}"]
        )
        reference_modified_by_file[target_file] = _run_git(
            repo_path, ["show", f"{head_ref}:{target_file}"]
        )
        reference_diff_by_file[target_file] = _run_git(
            repo_path, ["diff", f"{base_ref}..{head_ref}", "--", target_file]
        )

    if args.model:
        os.environ["DEFAULT_MODEL"] = args.model
    if args.model_endpoint:
        os.environ["DEFAULT_MODEL_ENDPOINT"] = args.model_endpoint

    nfr_focus = [entry.strip() for entry in args.nfr_focus.split(",") if entry.strip()]
    mcp_payload = asyncio.run(
        _run_mcp_workflow(
            repo_path=repo_path,
            issue_prompt=issue_prompt,
            target_files=target_files,
            original_code_by_file=original_code_by_file,
            nfr_focus=nfr_focus,
            temperature=args.temperature,
            seed=args.seed,
            log_lines=log_lines,
        )
    )

    apply_payload = (
        mcp_payload.get("apply") if isinstance(mcp_payload.get("apply"), dict) else None
    )
    apply_results = (
        mcp_payload.get("apply_results")
        if isinstance(mcp_payload.get("apply_results"), dict)
        else {}
    )
    generated_code_by_file = {
        path: str(payload.get("generated_code") or original_code_by_file.get(path, ""))
        for path, payload in apply_results.items()
        if isinstance(payload, dict)
    }
    for target_file in target_files:
        generated_code_by_file.setdefault(
            target_file, original_code_by_file.get(target_file, "")
        )

    generated_diff_by_file: dict[str, str] = {}
    for target_file in target_files:
        generated_diff_by_file[target_file] = "\n".join(
            difflib.unified_diff(
                original_code_by_file.get(target_file, "").splitlines(),
                generated_code_by_file.get(target_file, "").splitlines(),
                fromfile=f"{base_ref}:{target_file}",
                tofile="generated_solution",
                lineterm="",
            )
        )

    original_code = "\n\n".join(
        f"### FILE: {path}\n{original_code_by_file.get(path, '')}"
        for path in target_files
    )
    reference_modified_code = "\n\n".join(
        f"### FILE: {path}\n{reference_modified_by_file.get(path, '')}"
        for path in target_files
    )
    generated_code = "\n\n".join(
        f"### FILE: {path}\n{generated_code_by_file.get(path, '')}"
        for path in target_files
    )

    reference_unified_diff = "\n\n".join(
        [
            f"### FILE: {path}\n{reference_diff_by_file.get(path, '')}"
            for path in target_files
        ]
    )
    generated_unified_diff = "\n\n".join(
        [
            f"### FILE: {path}\n{generated_diff_by_file.get(path, '')}"
            for path in target_files
        ]
    )

    llm_debug_files: list[str] = []
    llm_debug_dir = None
    if args.metrics_llm_debug_dir:
        llm_debug_dir = Path(args.metrics_llm_debug_dir).resolve()
        llm_debug_files = _write_llm_debug_artifacts(
            debug_dir=llm_debug_dir,
            issue_prompt=issue_prompt,
            original_code=original_code,
            reference_modified_code=reference_modified_code,
            mcp_payload=mcp_payload,
        )
        log_lines.append(
            f"LLM debug artifacts written to {llm_debug_dir} ({len(llm_debug_files)} files)."
        )

    evaluator = ExperimentMetricsEvaluator()

    solid_delta_payload: dict[str, Any] | None = None
    if args.sonar_url and args.sonar_token and args.sonar_project_key:
        try:
            sonar_client = SonarQubeClient(
                base_url=args.sonar_url, token=args.sonar_token
            )

            rule_keys = [
                item.strip()
                for item in (args.sonar_rule_keys or "").split(",")
                if item.strip()
            ]
            severities = [
                item.strip().upper()
                for item in (args.sonar_severities or "").split(",")
                if item.strip()
            ]
            component_keys = [
                item.strip()
                for item in (args.sonar_component_keys or "").split(",")
                if item.strip()
            ]

            before_query = SonarIssueQuery(
                project_key=args.sonar_project_key,
                branch=args.sonar_before_branch,
                pull_request=args.sonar_before_pr,
                rule_keys=rule_keys,
                severities=severities,
                component_keys=component_keys or target_files,
            )
            after_query = SonarIssueQuery(
                project_key=args.sonar_project_key,
                branch=args.sonar_after_branch,
                pull_request=args.sonar_after_pr,
                rule_keys=rule_keys,
                severities=severities,
                component_keys=component_keys or target_files,
            )

            violations_before = sonar_client.count_issues(before_query)
            violations_after = sonar_client.count_issues(after_query)
            solid_delta = evaluator.solid_violation_delta(
                violations_before, violations_after
            )
            solid_delta_payload = {
                "violations_before": solid_delta.violations_before,
                "violations_after": solid_delta.violations_after,
                "delta": solid_delta.delta,
                "absolute_delta": solid_delta.absolute_delta,
                "source": "sonarqube",
            }
            log_lines.append(
                "SOLID delta from SonarQube computed: "
                f"before={violations_before}, after={violations_after}, delta={solid_delta.delta:.4f}"
            )
        except Exception as exc:
            log_lines.append(
                f"SOLID SonarQube evaluation skipped due to error: {type(exc).__name__}: {exc}"
            )

    original_metrics = evaluator.evaluate_all(
        generated_code=original_code,
        reference_code=original_code,
        requirements=[issue_prompt],
        artifacts=original_code,
        test_total=None,
    )
    modified_metrics = evaluator.evaluate_all(
        generated_code=generated_code,
        reference_code=original_code,
        requirements=[issue_prompt],
        artifacts=generated_code,
        test_total=None,
    )

    delta = {
        "solid_violation_delta": (
            solid_delta_payload.get("delta")
            if solid_delta_payload is not None
            else None
        ),
        "cognitive_complexity": (
            modified_metrics["complexity"]["cognitive_complexity"]
            - original_metrics["complexity"]["cognitive_complexity"]
        ),
        "cyclomatic_complexity": (
            modified_metrics["complexity"]["cyclomatic_complexity"]
            - original_metrics["complexity"]["cyclomatic_complexity"]
        ),
        "buse_weimer_proxy": (
            float(modified_metrics["readability"]["buse_weimer_proxy"])
            - float(original_metrics["readability"]["buse_weimer_proxy"])
        ),
    }

    report = {
        "run": {
            "execution_id": args.execution_id,
            "started_at": run_started,
            "finished_at": datetime.now(timezone.utc).isoformat(),
        },
        "issue": {
            "url": parsed_issue.url,
            "owner": parsed_issue.owner,
            "repo": parsed_issue.repo,
            "number": parsed_issue.issue_number,
            "title": issue.get("title"),
            "state": issue.get("state"),
        },
        "subject": {
            "repo_path": str(repo_path),
            "target_file": target_files[0] if target_files else None,
            "target_files": target_files,
            "target_file_count": len(target_files),
            "localizer": {
                "strategy_count": len(localizer.strategies),
                "details": localization.details,
            },
            "base_ref": base_ref,
            "head_ref": head_ref,
            "linked_pr_number": detected_pr,
            "generated_code_source": (
                "mcp_apply_plan_swe_code_change"
                if apply_payload
                and not apply_payload.get("used_fallback_to_original", False)
                else "original_code_fallback"
            ),
        },
        "run_config": {
            "github": {
                "api_base": gh_client.api_base,
                "authenticated": gh_client.authenticated,
                "detected_pr": detected_pr,
                "max_issue_comments": args.max_issue_comments,
            },
            "llm": {
                "model": args.model,
                "endpoint": args.model_endpoint,
                "temperature": args.temperature,
                "seed": args.seed,
                "notes": "Model and endpoint are passed through env vars to MCP tools.",
            },
            "mcp_server": {
                "command": mcp_payload["server"]["command"],
                "args": mcp_payload["server"]["args"],
                "cwd": mcp_payload["server"]["cwd"],
                "json_response": True,
            },
            "metrics": {
                "semantic_similarity_model": "microsoft/codebert-base",
                "requirements_coverage_strategy": "token-coverage",
                "test_pass_rate_source": "not-run",
                "readability": ["buse_weimer_proxy", "llm_evaluation"],
                "solid_delta_source": "sonarqube" if solid_delta_payload else "not-run",
                "sonarqube": {
                    "enabled": bool(
                        args.sonar_url and args.sonar_token and args.sonar_project_key
                    ),
                    "url": args.sonar_url,
                    "project_key": args.sonar_project_key,
                    "before_branch": args.sonar_before_branch,
                    "after_branch": args.sonar_after_branch,
                    "before_pr": args.sonar_before_pr,
                    "after_pr": args.sonar_after_pr,
                    "rule_keys": [
                        item.strip()
                        for item in (args.sonar_rule_keys or "").split(",")
                        if item.strip()
                    ],
                    "severities": [
                        item.strip().upper()
                        for item in (args.sonar_severities or "").split(",")
                        if item.strip()
                    ],
                    "component_keys": [
                        item.strip()
                        for item in (args.sonar_component_keys or "").split(",")
                        if item.strip()
                    ],
                },
                "llm_debug_dir": str(llm_debug_dir) if llm_debug_dir else None,
                "llm_debug_files": llm_debug_files,
            },
        },
        "mcp": {
            "tool_names": mcp_payload["tool_names"],
            "plan": mcp_payload["plan"],
            "context": mcp_payload["context"],
            "apply": mcp_payload.get("apply"),
            "apply_results": mcp_payload.get("apply_results", {}),
            "judgement": mcp_payload["judgement"],
        },
        "testability_gate": {
            "build_status": "not-run",
            "test_status": "not-run",
            "reason": "Gate not executed in this experiment run.",
        },
        "diff": {
            "reference_unified_diff": reference_unified_diff,
            "generated_unified_diff": generated_unified_diff,
            "reference_unified_diff_by_file": reference_diff_by_file,
            "generated_unified_diff_by_file": generated_diff_by_file,
        },
        "metrics": {
            "design_quality": {
                "solid_violation_delta": solid_delta_payload,
            },
            "original": original_metrics,
            "modified": modified_metrics,
            "delta": delta,
        },
        "logs": {
            "lines": log_lines,
        },
    }
    return report


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run generic MCP issue experiment")
    parser.add_argument("--issue-url", required=True, help="GitHub issue URL")
    parser.add_argument("--repo-path", required=True, help="Local repository path")
    parser.add_argument(
        "--max-target-files",
        type=int,
        default=5,
        help="Maximum number of files selected by the localizer.",
    )
    parser.add_argument(
        "--enable-nlp-localizer",
        action="store_true",
        help="Enable semantic NLP localizer strategy (TF-IDF cosine).",
    )
    parser.add_argument("--base-ref", default="HEAD", help="Git reference for baseline")
    parser.add_argument(
        "--head-ref",
        default=None,
        help="Git reference for candidate code. If omitted, PR ref is auto-resolved.",
    )
    parser.add_argument(
        "--pull-request-number",
        type=int,
        default=None,
        help="Optional explicit pull request number linked to the issue.",
    )
    parser.add_argument(
        "--auto-detect-pr",
        action="store_true",
        help="Try to detect linked PR from issue references.",
    )
    parser.add_argument(
        "--max-issue-comments",
        type=int,
        default=20,
        help="Maximum number of comments to fetch from GitHub issue API.",
    )
    parser.add_argument(
        "--github-token", default=None, help="GitHub token for API requests"
    )
    parser.add_argument(
        "--nfr-focus",
        default="Reliability,Maintainability,Security",
        help="Comma-separated NFR focus list",
    )
    parser.add_argument(
        "--model",
        default=os.getenv("DEFAULT_MODEL"),
        help="Model name for MCP tools",
    )
    parser.add_argument(
        "--model-endpoint",
        default=os.getenv("DEFAULT_MODEL_ENDPOINT"),
        help="Model endpoint for MCP tools",
    )
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--sonar-url",
        default=os.getenv("SONAR_HOST_URL"),
        help="SonarQube base URL (for example https://sonar.mycompany.com)",
    )
    parser.add_argument(
        "--sonar-token",
        default=os.getenv("SONAR_TOKEN"),
        help="SonarQube user token",
    )
    parser.add_argument(
        "--sonar-project-key",
        default=os.getenv("SONAR_PROJECT_KEY"),
        help="SonarQube project key",
    )
    parser.add_argument(
        "--sonar-before-branch",
        default=None,
        help="Branch name for baseline count",
    )
    parser.add_argument(
        "--sonar-after-branch",
        default=None,
        help="Branch name for treatment count",
    )
    parser.add_argument(
        "--sonar-before-pr",
        default=None,
        help="PR key/id for baseline count (alternative to branch)",
    )
    parser.add_argument(
        "--sonar-after-pr",
        default=None,
        help="PR key/id for treatment count (alternative to branch)",
    )
    parser.add_argument(
        "--sonar-rule-keys",
        default="",
        help="Comma-separated Sonar rule keys used as SOLID proxy",
    )
    parser.add_argument(
        "--sonar-severities",
        default="MAJOR,CRITICAL,BLOCKER",
        help="Comma-separated severities filter for Sonar issues",
    )
    parser.add_argument(
        "--sonar-component-keys",
        default="",
        help="Comma-separated Sonar component keys to scope issue counting",
    )
    parser.add_argument(
        "--out-json",
        default="reports/openssl_issue_31332_experiment.json",
        help="Path to detailed JSON report",
    )
    parser.add_argument(
        "--out-md",
        default="reports/openssl_issue_31332_summary.md",
        help="Path to markdown summary",
    )
    parser.add_argument(
        "--out-csv",
        default="reports/openssl_issue_31332_metrics.csv",
        help="Path to CSV metrics",
    )
    parser.add_argument(
        "--out-log",
        default="reports/openssl_issue_31332_execution.log",
        help="Path to execution log",
    )
    parser.add_argument(
        "--metrics-llm-debug-dir",
        default=None,
        help=(
            "Optional folder to export per-call markdown debug files with raw LLM "
            "responses and extracted code blocks."
        ),
    )
    parser.add_argument(
        "--execution-id",
        default=None,
        help=(
            "Execution identifier used in metadata and output templates. "
            "Defaults to UTC timestamp when omitted."
        ),
    )
    parser.add_argument(
        "--clean-output",
        action="store_true",
        help="Delete output artifacts for the selected output paths before writing new ones.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    workspace_root = Path(__file__).resolve().parents[2]
    load_dotenv(workspace_root / ".env")
    parser = _build_parser()
    args = parser.parse_args(argv)

    execution_id = args.execution_id or _default_execution_id()
    args.execution_id = execution_id
    args.out_json = _render_with_execution_id(args.out_json, execution_id)
    args.out_md = _render_with_execution_id(args.out_md, execution_id)
    args.out_csv = _render_with_execution_id(args.out_csv, execution_id)
    args.out_log = _render_with_execution_id(args.out_log, execution_id)
    args.metrics_llm_debug_dir = _render_with_execution_id(
        args.metrics_llm_debug_dir,
        execution_id,
    )

    out_json = Path(args.out_json).resolve()
    out_md = Path(args.out_md).resolve()
    out_csv = Path(args.out_csv).resolve()
    out_log = Path(args.out_log).resolve()

    if args.clean_output:
        out_json.unlink(missing_ok=True)
        out_md.unlink(missing_ok=True)
        out_csv.unlink(missing_ok=True)
        out_log.unlink(missing_ok=True)
        if args.metrics_llm_debug_dir:
            debug_dir = Path(args.metrics_llm_debug_dir).resolve()
            for old_md in debug_dir.glob("*.md"):
                old_md.unlink(missing_ok=True)

    report = _run_experiment(args)
    rows = metrics_rows(report)

    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    write_csv_report(out_csv, rows)
    write_log_report(out_log, report["logs"]["lines"])
    write_markdown_report(out_md, report, rows, out_json, out_csv, out_log)

    judgement = report["mcp"].get("judgement")
    if isinstance(judgement, dict):
        verdict = judgement.get("overall_verdict", "n/a")
    else:
        verdict = "n/a"

    print("=== Experiment completed ===")
    print(f"Execution ID: {execution_id}")
    print(f"Issue: {report['issue']['url']}")
    print(f"Target files: {report['subject'].get('target_file_count', 1)}")
    print(f"Verdict: {verdict}")
    print(f"JSON report: {out_json}")
    print(f"Markdown report: {out_md}")
    print(f"CSV report: {out_csv}")
    print(f"Log report: {out_log}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

