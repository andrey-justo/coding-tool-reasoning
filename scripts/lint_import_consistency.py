from __future__ import annotations

import ast
import sys
from pathlib import Path
from typing import Iterable


DEFAULT_TARGETS = ("src", "tests")


class ImportLintViolation:
    def __init__(self, file_path: Path, line: int, message: str) -> None:
        self.file_path = file_path
        self.line = line
        self.message = message

    def __str__(self) -> str:
        return f"{self.file_path}:{self.line}: {self.message}"


def iter_python_files(targets: Iterable[str]) -> Iterable[Path]:
    for target in targets:
        root = Path(target)
        if not root.exists():
            continue
        for file_path in root.rglob("*.py"):
            if any(part in {".venv", "__pycache__", ".git"} for part in file_path.parts):
                continue
            yield file_path


def lint_file(file_path: Path) -> list[ImportLintViolation]:
    violations: list[ImportLintViolation] = []
    source = file_path.read_text(encoding="utf-8")

    try:
        tree = ast.parse(source, filename=str(file_path))
    except SyntaxError as exc:
        violations.append(
            ImportLintViolation(
                file_path=file_path,
                line=exc.lineno or 1,
                message=f"Syntax error while parsing file: {exc.msg}",
            )
        )
        return violations

    parent_map: dict[ast.AST, ast.AST] = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parent_map[child] = parent

    for node in ast.walk(tree):
        if not isinstance(node, (ast.Import, ast.ImportFrom)):
            continue

        parent = parent_map.get(node)
        if isinstance(parent, ast.Try):
            violations.append(
                ImportLintViolation(
                    file_path=file_path,
                    line=node.lineno,
                    message="Import statements inside try/except are not allowed.",
                )
            )
            continue

        if not isinstance(parent, ast.Module):
            violations.append(
                ImportLintViolation(
                    file_path=file_path,
                    line=node.lineno,
                    message="Import statements must be declared at module top-level.",
                )
            )

    return violations


def main() -> int:
    targets = tuple(sys.argv[1:]) or DEFAULT_TARGETS
    violations: list[ImportLintViolation] = []

    for file_path in iter_python_files(targets):
        violations.extend(lint_file(file_path))

    if not violations:
        print("Import consistency lint passed.")
        return 0

    for violation in sorted(violations, key=lambda item: (str(item.file_path), item.line)):
        print(violation)

    print(f"\nFound {len(violations)} import lint violation(s).")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
