"""Single CLI entry point for MCP and experiment workflows.

This module is the only runtime entrypoint and dispatches to:
- MCP server runtime
- Reproducibility experiment runner
"""

from __future__ import annotations

import argparse

from mcp.server.fastmcp import FastMCP
from src.evaluation.reproducibility_experiment import (
    parse_reproducibility_args,
    run_reproducibility_from_args,
)
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

    return parser


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

    parser.error(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    main()
