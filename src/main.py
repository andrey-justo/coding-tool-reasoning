"""Single CLI entry point for MCP and experiment workflows.

This module is the only runtime entrypoint and dispatches to:
- MCP server runtime
- Reproducibility experiment runner
"""

from __future__ import annotations

import argparse
from pathlib import Path

import yaml
from mcp.server.fastmcp import FastMCP

from src.evaluation.reproducibility_experiment import (
    parse_reproducibility_args,
    run_reproducibility_from_args,
)
from src.experiments.issue_mcp_experiment import main as run_issue_experiment
from src.mcp.swe_mcp_server import register_swe_tools_on_mcp


def _run_mcp_server() -> None:
    mcp = FastMCP("SWE-NFR-MCP", json_response=True)
    register_swe_tools_on_mcp(mcp)
    mcp.run()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Main runtime entrypoint for SWE MCP tools and experiments."
    )
    subparsers = parser.add_subparsers(dest="command", required=False)

    subparsers.add_parser("mcp-server", help="Run the SWE MCP server.")

    reproducibility_parser = subparsers.add_parser(
        "reproducibility",
        help="Run the RQ2 reproducibility experiment.",
    )
    reproducibility_parser.add_argument(
        "repro_args",
        nargs=argparse.REMAINDER,
        help="Arguments forwarded to reproducibility runner (e.g. --prompt ...).",
    )

    issue_parser = subparsers.add_parser(
        "issue-experiment",
        help="Run issue-centric MCP experiment.",
    )
    issue_parser.add_argument(
        "issue_args",
        nargs=argparse.REMAINDER,
        help="Arguments forwarded to issue experiment runner.",
    )

    config_parser = subparsers.add_parser(
        "run-config",
        help="Run commands using a YAML config file.",
    )
    config_parser.add_argument(
        "--config",
        required=True,
        help="Path to YAML config file.",
    )

    return parser


def _yaml_config_to_argv(config_payload: dict) -> tuple[str, list[str]]:
    command = str(config_payload.get("command") or "mcp-server").strip()
    if not command:
        command = "mcp-server"

    raw_args = config_payload.get("args")
    if isinstance(raw_args, list):
        return command, [str(item) for item in raw_args]

    if not isinstance(raw_args, dict):
        return command, []

    argv: list[str] = []
    for key, value in raw_args.items():
        if value is None:
            continue
        flag = f"--{str(key).replace('_', '-')}"
        if isinstance(value, bool):
            if value:
                argv.append(flag)
            continue
        if isinstance(value, list):
            if value:
                argv.extend([flag, ",".join(str(item) for item in value)])
            continue
        argv.extend([flag, str(value)])
    return command, argv


def _run_from_yaml(config_path: str) -> None:
    payload = yaml.safe_load(Path(config_path).read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise ValueError("YAML config root must be a mapping/object.")

    command, forwarded_args = _yaml_config_to_argv(payload)

    if command == "mcp-server":
        _run_mcp_server()
        return

    if command == "reproducibility":
        parsed = parse_reproducibility_args(forwarded_args)
        run_reproducibility_from_args(parsed)
        return

    if command == "issue-experiment":
        run_issue_experiment(forwarded_args)
        return

    raise ValueError(f"Unsupported command in YAML config: {command}")


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    # SWE MCP is the primary runtime path for this project.
    if args.command in (None, "mcp-server"):
        _run_mcp_server()
        return

    if args.command == "reproducibility":
        forwarded_args = args.repro_args or []
        parsed = parse_reproducibility_args(forwarded_args)
        run_reproducibility_from_args(parsed)
        return

    if args.command == "issue-experiment":
        forwarded_args = args.issue_args or []
        run_issue_experiment(forwarded_args)
        return

    if args.command == "run-config":
        _run_from_yaml(args.config)
        return

    parser.error(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    main()
