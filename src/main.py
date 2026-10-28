"""Single CLI entry point for MCP and experiment workflows.

This module is the only runtime entrypoint and dispatches to:
- MCP server runtime
- Reproducibility experiment runner
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import yaml
from mcp.server.fastmcp import FastMCP

from src.evaluation.reproducibility_experiment import (
    parse_reproducibility_args,
    run_reproducibility_from_args,
)
from src.experiments.issue_mcp_experiment import main as run_issue_experiment
from src.experiments.repair_replay import run_repair_replay
from src.llm_client.copilot_sdk_client import CopilotSDKClient
from src.mcp.swe_mcp_server import register_swe_tools_on_mcp


def _configure_mcp_logging() -> None:
    """Format runtime diagnostics on stderr while reducing MCP transport noise."""

    logging.basicConfig(
        level=logging.INFO,
        format=(
            "%(asctime)s [%(levelname)s] %(name)s "
            "(%(pathname)s:%(lineno)d): %(message)s"
        ),
        datefmt="%Y-%m-%dT%H:%M:%S%z",
    )

    noisy_loggers = [
        "mcp.server.lowlevel.server",
        "mcp.server.session",
        "mcp.shared.session",
        "src.service.swe_knowledge_base_service",
    ]
    for logger_name in noisy_loggers:
        logging.getLogger(logger_name).setLevel(logging.WARNING)


def _run_mcp_server() -> None:
    mcp = FastMCP("SWE-NFR-MCP", json_response=True, log_level="WARNING")
    register_swe_tools_on_mcp(mcp)
    mcp.run()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Main runtime entrypoint for SWE MCP tools and experiments."
    )
    subparsers = parser.add_subparsers(dest="command", required=False)

    subparsers.add_parser("mcp-server", help="Run the SWE MCP server.")
    subparsers.add_parser(
        "copilot-models",
        help="List models available to the authenticated Copilot account.",
    )

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

    replay_parser = subparsers.add_parser(
        "repair-replay", help="Probe repairs against a frozen experiment candidate."
    )
    replay_parser.add_argument("--report", type=Path, required=True)
    replay_parser.add_argument("--out-json", type=Path, required=True)
    replay_parser.add_argument("--max-attempts", type=int, default=3)
    replay_parser.add_argument("--timeout-seconds", type=int, default=300)
    replay_parser.add_argument("--model")
    replay_parser.add_argument("--run-tests", action=argparse.BooleanOptionalAction, default=True)
    replay_parser.add_argument("--candidate-report", type=Path)
    replay_parser.add_argument("--candidate-attempt", type=int)
    replay_parser.add_argument("--repair-mode", choices=["loop", "tree"], default="loop")
    replay_parser.add_argument("--repair-concurrency", type=int, default=3)
    replay_parser.add_argument("--repair-agent-max-seconds", type=int, default=300)

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
    logging.getLogger(__name__).info(
        "Starting %s using config %s", command, config_path
    )

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


def _dispatch() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    # SWE MCP is the primary runtime path for this project.
    if args.command in (None, "mcp-server"):
        _run_mcp_server()
        return

    if args.command == "copilot-models":
        for model in CopilotSDKClient.list_models():
            print(f"{model['id']}\t{model['name']}")
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

    if args.command == "repair-replay":
        result = run_repair_replay(
            report_path=args.report,
            output_path=args.out_json,
            max_attempts=args.max_attempts,
            timeout_seconds=args.timeout_seconds,
            model=args.model,
            max_seconds=args.repair_agent_max_seconds,
            mode=args.repair_mode,
            concurrency=args.repair_concurrency,
            run_tests=args.run_tests,
            candidate_report=args.candidate_report,
            candidate_attempt=args.candidate_attempt,
        )
        print(f"Replay accepted: {result['accepted']}; {result['stopped_reason']}")
        print(f"JSON report: {args.out_json.resolve()}")
        return

    parser.error(f"Unsupported command: {args.command}")


def main() -> None:
    _configure_mcp_logging()
    try:
        _dispatch()
    finally:
        CopilotSDKClient.shutdown()


if __name__ == "__main__":
    main()
