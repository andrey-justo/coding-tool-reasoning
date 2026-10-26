from __future__ import annotations

import re
from pathlib import Path

import pytest

from src.experiments.issue_mcp_experiment import (
    _as_pretty_json,
    _coerce_json,
    _count_apply_outcomes,
    _default_execution_id,
    _enforce_verification_verdict,
    _extract_code_blocks,
    _parse_issue_url,
    _render_with_execution_id,
    _write_llm_debug_artifacts,
)


def test_default_execution_id_format() -> None:
    execution_id = _default_execution_id()
    assert re.match(r"^\d{8}T\d{6}Z$", execution_id)


def test_count_apply_outcomes_aggregates_states_and_legacy_payloads() -> None:
    counts = _count_apply_outcomes(
        {
            "a.cs": {"apply_outcome": "modified"},
            "b.cs": {"apply_outcome": "unchanged_model_output"},
            "c.cs": {"apply_outcome": "modified"},
            "d.cs": {"used_fallback_to_original": True},
            "e.cs": {"used_fallback_to_original": False},
            "f.cs": "not-a-dict",
        }
    )

    assert counts == {"modified": 3, "unchanged_model_output": 2}



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


def test_enforce_verification_verdict_rejects_syntax_and_build_failures() -> None:
    result = _enforce_verification_verdict(
        judgement={
            "overall_verdict": "acceptable",
            "rationale": "LLM considered the change acceptable.",
        },
        apply_results={
            "src/Broken.cs": {
                "syntax_validation": {"rejected_invalid_generation": True}
            }
        },
        verification_gate={
            "testability_gate": {
                "build_status": "fail",
                "test_status": "not-run",
            }
        },
    )

    assert result["overall_verdict"] == "rejected"
    assert result["llm_overall_verdict"] == "acceptable"
    assert len(result["verification_blocking_reasons"]) == 2
    assert "Automated verification rejected" in result["rationale"]


def test_enforce_verification_verdict_preserves_non_blocked_judgement() -> None:
    judgement = {"overall_verdict": "acceptable", "rationale": "Verified."}

    result = _enforce_verification_verdict(
        judgement=judgement,
        apply_results={"src/Valid.cs": {"error": None}},
        verification_gate={
            "testability_gate": {
                "build_status": "pass",
                "test_status": "pass",
            }
        },
    )

    assert result == judgement


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
