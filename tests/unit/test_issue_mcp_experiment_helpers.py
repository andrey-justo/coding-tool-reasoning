from __future__ import annotations

import re
from pathlib import Path

import pytest

from src.experiments.issue_mcp_experiment import (
    _as_pretty_json,
    _coerce_json,
    _default_execution_id,
    _extract_code_blocks,
    _parse_issue_url,
    _render_with_execution_id,
    _write_llm_debug_artifacts,
)


def test_default_execution_id_format() -> None:
    execution_id = _default_execution_id()
    assert re.match(r"^\d{8}T\d{6}Z$", execution_id)


def test_render_with_execution_id_supports_errors_and_none() -> None:
    assert _render_with_execution_id(None, "x") is None
    assert _render_with_execution_id("out_{execution_id}.json", "abc") == "out_abc.json"
    assert _render_with_execution_id("{", "abc") == "{"


def test_coerce_json_and_extract_code_blocks() -> None:
    assert _coerce_json('{"a": 1}') == {"a": 1}
    assert _coerce_json("not-json") == "not-json"
    assert _extract_code_blocks(None) == []

    blocks = _extract_code_blocks("```python\nprint('x')\n```")
    assert len(blocks) == 1
    assert blocks[0]["language"] == "python"


def test_as_pretty_json_fallback_to_str() -> None:
    class _Unserializable:
        pass

    text = _as_pretty_json(_Unserializable())
    assert "_Unserializable" in text


def test_parse_issue_url_valid_and_invalid() -> None:
    parsed = _parse_issue_url("https://github.com/org/repo/issues/123")
    assert parsed.owner == "org"
    assert parsed.repo == "repo"
    assert parsed.issue_number == 123

    with pytest.raises(ValueError):
        _parse_issue_url("https://example.com/not-github")


def test_write_llm_debug_artifacts_creates_markdown_files(tmp_path: Path) -> None:
    payload = {
        "plan": {"llm_prompt": "plan prompt", "llm_raw_response": "{}"},
        "context": {"x": 1},
        "apply": {
            "prompt": "apply prompt",
            "raw_response": "```python\nprint('ok')\n```",
            "generated_code": "print('ok')",
            "used_fallback_to_original": False,
            "chunked": False,
            "chunk_count": 1,
            "chunk_errors": [],
            "error": None,
        },
        "judgement": {"llm_prompt": "judge", "llm_raw_response": "{}"},
    }

    files = _write_llm_debug_artifacts(
        debug_dir=tmp_path,
        issue_prompt="issue",
        original_code="print('old')",
        reference_modified_code="print('ref')",
        mcp_payload=payload,
    )

    assert files
    assert (tmp_path / "05-original_vs_generated_code.md").exists()
    assert (tmp_path / "06-generated_code_diff.md").exists()
