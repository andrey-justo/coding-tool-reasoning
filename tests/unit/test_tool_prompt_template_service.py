from __future__ import annotations

from pathlib import Path

import pytest

from src.service.tool_prompt_template_service import (
    ToolPromptTemplateError,
    ToolPromptTemplateService,
)


def test_render_replaces_placeholders(tmp_path: Path) -> None:
    tool_dir = tmp_path / "tool"
    tool_dir.mkdir()
    (tool_dir / "demo.md").write_text(
        "file={{ TARGET_PATH }} attempt={{ ATTEMPT }}/{{ MAX_ATTEMPTS }}",
        encoding="utf-8",
    )

    service = ToolPromptTemplateService(tmp_path)
    rendered = service.render(
        "demo",
        {"TARGET_PATH": "a/b.cs", "ATTEMPT": "1", "MAX_ATTEMPTS": "2"},
    )

    assert rendered == "file=a/b.cs attempt=1/2"


def test_render_raises_on_missing_placeholder_values(tmp_path: Path) -> None:
    tool_dir = tmp_path / "tool"
    tool_dir.mkdir()
    (tool_dir / "demo.md").write_text("{{ A }}{{ B }}", encoding="utf-8")

    service = ToolPromptTemplateService(tmp_path)
    with pytest.raises(ToolPromptTemplateError) as excinfo:
        service.render("demo", {"A": "x"})

    assert "B" in str(excinfo.value)


def test_load_raises_when_template_missing(tmp_path: Path) -> None:
    service = ToolPromptTemplateService(tmp_path)
    with pytest.raises(ToolPromptTemplateError):
        service.load("absent")


def test_packaged_syntax_repair_template_renders() -> None:
    rendered = ToolPromptTemplateService().render(
        "syntax_repair",
        {
            "TARGET_PATH": "src/Hub.cs",
            "ATTEMPT": "1",
            "MAX_ATTEMPTS": "2",
            "DIAGNOSTICS_JSON": "[]",
            "ORIGINAL_CODE": "class A {}",
            "GENERATED_CODE": "class A {",
        },
    )

    assert "Target file: src/Hub.cs" in rendered
    assert "Repair attempt: 1/2" in rendered
    assert "{{" not in rendered
