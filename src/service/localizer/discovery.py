from __future__ import annotations

import os
from pathlib import Path

from src.service.localizer.constants import _CODE_EXTENSIONS, _EXCLUDED_DIRS


def discover_repository_code_files(repo_path: Path) -> list[str]:
    files: list[str] = []
    for root, dirs, filenames in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in _EXCLUDED_DIRS]
        for name in filenames:
            path = Path(root) / name
            if path.suffix.lower() not in _CODE_EXTENSIONS:
                continue
            rel = path.relative_to(repo_path).as_posix()
            files.append(rel)
    return sorted(files)
