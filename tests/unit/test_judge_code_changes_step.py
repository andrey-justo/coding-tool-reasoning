from __future__ import annotations

import asyncio

import pytest

from src.mcp.tools.judge_code_changes_step import JudgeCodeChangesStep
from src.models.code_gen_plan import CodeGenPlan
from src.models.swe_config import SweMcpConfig
from src.models.swe_context import SweContext


class _FakeKB:
    def __init__(self):
        self.loaded = False

    def load(self):
        self.loaded = True


class _FakeService:
    def __init__(self, kb, llm_client, config):
        self.kb = kb
        self.llm_client = llm_client
        self.config = config

    def explain_change(self, swe_context, original_code, modified_code):
        return {
            "ctx": swe_context,
            "original": original_code,
            "modified": modified_code,
        }


def test_constructor_raises_when_kb_and_paths_missing() -> None:
    with pytest.raises(ValueError, match="Either 'kb' must be provided"):
        JudgeCodeChangesStep(kb=None, ground_data_dir=None, linked_data_dir=None)


def test_constructor_loads_kb_and_run_delegates(monkeypatch) -> None:
    fake_kb = _FakeKB()

    monkeypatch.setattr(
        "src.mcp.tools.judge_code_changes_step.ExplanationService",
        _FakeService,
    )

    step = JudgeCodeChangesStep(
        kb=fake_kb,
        llm_client=object(),
        config=SweMcpConfig(),
    )

    assert fake_kb.loaded is True

    ctx = SweContext(
        plan=CodeGenPlan(problem_description="p"),
        swe_summary="s",
        templates=[],
    )
    result = asyncio.run(
        step.run(swe_context=ctx, original_code="a", modified_code="b")
    )

    assert result["original"] == "a"
    assert result["modified"] == "b"
    assert result["ctx"] == ctx
