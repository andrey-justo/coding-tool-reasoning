from __future__ import annotations

import re
from pathlib import Path
from typing import Mapping, Optional

_PLACEHOLDER_PATTERN = re.compile(r"\{\{\s*([A-Za-z0-9_.-]+)\s*\}\}")

_TOOL_TEMPLATE_SUBDIR = "tool"
_DEFAULT_TEMPLATES_ROOT = Path(__file__).resolve().parents[2] / "knowledge" / "template"


class ToolPromptTemplateError(RuntimeError):
    """Raised when a tool prompt template cannot be loaded or rendered."""


class ToolPromptTemplateService:
    """Load and render prompt templates used by MCP tools.

    Tool templates live under ``<templates_root>/tool/<name>.md`` so they are not
    picked up by the concern-template loader, which globs ``<templates_root>/*.md``
    and injects every match into generation prompts.
    """

    def __init__(self, templates_root: Optional[str | Path] = None) -> None:
        self._templates_root = (
            Path(templates_root) if templates_root else _DEFAULT_TEMPLATES_ROOT
        )

    def template_path(self, name: str) -> Path:
        return self._templates_root / _TOOL_TEMPLATE_SUBDIR / f"{name}.md"

    def load(self, name: str) -> str:
        path = self.template_path(name)
        try:
            return path.read_text(encoding="utf-8")
        except OSError as exc:
            raise ToolPromptTemplateError(
                f"Tool prompt template '{name}' could not be read from {path}: {exc}"
            ) from exc

    def render(self, name: str, values: Mapping[str, str]) -> str:
        content = self.load(name)
        placeholders = set(_PLACEHOLDER_PATTERN.findall(content))
        missing = sorted(placeholders - set(values))
        if missing:
            raise ToolPromptTemplateError(
                f"Tool prompt template '{name}' is missing values for placeholders: "
                + ", ".join(missing)
            )

        def _replace(match: re.Match[str]) -> str:
            return str(values[match.group(1)])

        return _PLACEHOLDER_PATTERN.sub(_replace, content)
