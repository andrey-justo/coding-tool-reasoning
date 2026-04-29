"""Shared smoke-test helpers and fixtures."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SMOKE_PROMPT_LOG_DIR = REPO_ROOT / "tests" / ".artifacts" / "prompt-logs"

def resolve_prompt_output_root(env_var: str, default: Path) -> Path:
    configured = os.environ.get(env_var)
    if configured:
        output_path = Path(configured)
        if not output_path.is_absolute():
            output_path = REPO_ROOT / output_path
        return output_path
    return default


def reset_output_root(output_root: Path) -> None:
    if output_root.exists():
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True, exist_ok=True)
