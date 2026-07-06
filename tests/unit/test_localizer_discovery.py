from __future__ import annotations

from pathlib import Path

from src.service.localizer.discovery import discover_repository_code_files


def test_discover_repository_code_files_filters_extensions_and_excluded_dirs(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir(parents=True, exist_ok=True)
    (tmp_path / "src" / "a.py").write_text("print('x')", encoding="utf-8")
    (tmp_path / "src" / "b.txt").write_text("ignore", encoding="utf-8")

    (tmp_path / "docs").mkdir(parents=True, exist_ok=True)
    (tmp_path / "docs" / "ignored.py").write_text("print('ignored')", encoding="utf-8")

    (tmp_path / "node_modules" / "pkg").mkdir(parents=True, exist_ok=True)
    (tmp_path / "node_modules" / "pkg" / "x.js").write_text("console.log(1)", encoding="utf-8")

    found = discover_repository_code_files(tmp_path)

    assert "src/a.py" in found
    assert "src/b.txt" not in found
    assert "docs/ignored.py" not in found
    assert all(not p.startswith("node_modules/") for p in found)
