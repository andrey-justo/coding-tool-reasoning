from __future__ import annotations

import sys

from src.experiments.issue_mcp_experiment import main as generic_main


DEFAULT_ARGS = [
    "--issue-url",
    "https://github.com/openssl/openssl/issues/31332",
    "--repo-path",
    "../openssl-subject",
    "--auto-detect-pr",
]


def main() -> int:
    argv = sys.argv[1:]
    if argv:
        return generic_main(argv)
    return generic_main(DEFAULT_ARGS)


if __name__ == "__main__":
    raise SystemExit(main())
