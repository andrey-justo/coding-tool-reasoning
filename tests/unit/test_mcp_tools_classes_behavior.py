from __future__ import annotations

import logging
from types import SimpleNamespace
from unittest.mock import MagicMock

from src.mcp.tools.apply_plan_swe_code_change_tool import ApplyPlanSweCodeChangeTool
from src.mcp.tools.judge_swe_code_change_tool import JudgeSweCodeChangeTool
from src.models.code_gen_plan import CodeGenPlan
from src.models.swe_context import SweContext
from src.models.swe_explanation import SweCodeChangeExplanation
from src.models.utility_decisions import SemanticReview
from src.service.syntax_validator import SyntaxValidator


class _FakeLlmSuccess:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def chat(self, prompt: str, **kwargs) -> str:
        self.calls.append({"prompt": prompt, "kwargs": kwargs})
        return "```python\nprint('updated')\n```"


class _FakeLlmFailure:
    def chat(self, prompt: str, **kwargs) -> str:
        raise RuntimeError("llm unavailable")


class _FakeLlmChunked:
    def __init__(self) -> None:
        self.calls = 0

    def chat(self, prompt: str, **kwargs) -> str:
        self.calls += 1
        return "```\nUPDATED_CHUNK\n```"


class _FakeLlmInvalidThenRepair:
    last_instance = None

    def __init__(self) -> None:
        self.calls = 0
        type(self).last_instance = self

    def chat(self, prompt: str, **kwargs) -> str:
        self.calls += 1
        if self.calls == 1:
            return "```csharp\npublic class Example { public void Run( { }\n```"
        return (
            "```csharp\n"
            'public class Example { public void Run() { Console.WriteLine("updated"); } }\n'
            "```"
        )


class _FakeLlmAlwaysInvalid:
    def chat(self, prompt: str, **kwargs) -> str:
        return "```csharp\npublic class Example { public void Run( { }\n```"


def _build_swe_context() -> SweContext:
    return SweContext(
        plan=CodeGenPlan(
            problem_description="Apply planned change",
            target_language="python",
            nfr_focus=["Maintainability"],
            high_level_steps=["step"],
        ),
        swe_summary="summary context",
        templates=[],
        security_context="security context",
    )


def _build_registry(
    llm_cls, *, max_single_shot_code_chars: int = 12000, chunk_lines: int = 3
):
    execution_cfg = SimpleNamespace(
        max_summary_chars=200,
        max_security_context_chars=120,
        max_single_shot_code_chars=max_single_shot_code_chars,
        chunk_lines=chunk_lines,
    )
    cfg = SimpleNamespace(execution=execution_cfg)
    ctx = SimpleNamespace(config=cfg, kb="kb")

    return SimpleNamespace(
        _llm_client_cls=llm_cls,
        _create_swe_server_context=lambda: ctx,
        _logger=SimpleNamespace(warning=lambda *args, **kwargs: None),
        _explanation_service_cls=None,
    )


def test_apply_plan_tool_executes_single_shot_and_forwards_chat_kwargs() -> None:
    registry = _build_registry(_FakeLlmSuccess)
    tool = ApplyPlanSweCodeChangeTool(registry)

    result = tool.execute(
        swe_context=_build_swe_context(),
        original_code="print('old')",
        target_file="src/file.py",
        temperature=0.2,
        seed=42,
    )

    assert result["target_file"] == "src/file.py"
    assert result["chunked"] is False
    assert "print('updated')" in result["generated_code"]
    assert result["used_fallback_to_original"] is False
    assert result["apply_outcome"] == "modified"


def test_apply_plan_tool_returns_fallback_on_llm_error(caplog) -> None:
    registry = _build_registry(_FakeLlmFailure)
    registry._logger = logging.getLogger(__name__)
    tool = ApplyPlanSweCodeChangeTool(registry)

    original = "print('old')"
    result = tool.execute(
        swe_context=_build_swe_context(),
        original_code=original,
    )

    assert result["generated_code"] == original
    assert result["used_fallback_to_original"] is True
    assert result["chunked"] is False
    assert "RuntimeError" in result["error"]
    assert result["apply_outcome"] == "generation_error_fallback"
    assert caplog.records[-1].exc_info is not None
    assert "Traceback (most recent call last)" in caplog.text
    assert "RuntimeError: llm unavailable" in caplog.text


def test_chunk_errors_log_tracebacks_and_source_context(caplog) -> None:
    registry = _build_registry(
        _FakeLlmFailure, max_single_shot_code_chars=5, chunk_lines=2
    )
    registry._logger = logging.getLogger(__name__)
    original = "\n".join(["a", "b", "c", "d"])
    result = ApplyPlanSweCodeChangeTool(registry).execute(
        swe_context=_build_swe_context(),
        original_code=original,
        target_file="src/example.py",
    )
    assert result["generated_code"] == original
    chunk_records = [
        record
        for record in caplog.records
        if "Chunk generation failed" in record.message
    ]
    assert len(chunk_records) == 2
    assert all(record.exc_info is not None for record in chunk_records)
    assert "src/example.py (chunk 1/2, lines 1-2)" in caplog.text


def test_apply_plan_tool_chunked_mode_uses_multiple_chunks() -> None:
    registry = _build_registry(
        _FakeLlmChunked, max_single_shot_code_chars=5, chunk_lines=2
    )
    tool = ApplyPlanSweCodeChangeTool(registry)

    original = "\n".join(["a", "b", "c", "d", "e"])
    result = tool.execute(
        swe_context=_build_swe_context(),
        original_code=original,
    )

    assert result["chunked"] is True
    assert result["chunk_count"] >= 2
    assert "UPDATED_CHUNK" in result["generated_code"]


def test_parallel_chunk_results_keep_order_and_preserve_failed_chunks(caplog):
    llm = SimpleNamespace(
        chat=MagicMock(),
        chat_batch=MagicMock(
            return_value=[
                "```python\na = 1\nb = 1\n```",
                RuntimeError("middle chunk failed"),
                "```python\ne = 1\nf = 1\n```",
            ]
        ),
    )
    registry = _build_registry(lambda: llm, max_single_shot_code_chars=5, chunk_lines=2)
    registry._logger = logging.getLogger(__name__)
    registry._create_swe_server_context().config.execution.max_generation_concurrency = 3
    result = ApplyPlanSweCodeChangeTool(registry).execute(
        swe_context=_build_swe_context(),
        original_code="a = 0\nb = 0\nc = 0\nd = 0\ne = 0\nf = 0",
        target_file="example.py",
    )
    assert result["generated_code"] == ("a = 1\nb = 1\nc = 0\nd = 0\ne = 1\nf = 1")
    assert result["chunk_errors"][0]["chunk_index"] == 2
    assert "middle chunk failed" in caplog.text
    llm.chat.assert_not_called()
    llm.chat_batch.assert_called_once()
    assert llm.chat_batch.call_args.kwargs["max_concurrency"] == 3
    assert len(llm.chat_batch.call_args.args[0]) == 3


def test_apply_plan_tool_helpers_cover_edge_cases() -> None:
    assert ApplyPlanSweCodeChangeTool._split_code_chunks("", chunk_lines=5) == [
        {"start": 1, "end": 1, "code": ""}
    ]
    assert ApplyPlanSweCodeChangeTool._normalize_generated_formatting("x", "") == "x"
    assert (
        ApplyPlanSweCodeChangeTool._strip_transport_bom("\ufeffclass C {}")
        == "class C {}"
    )
    assert (
        ApplyPlanSweCodeChangeTool._strip_transport_bom("ï»¿class C {}") == "class C {}"
    )


def _mock_reviews(monkeypatch, *approvals):
    results = iter(
        SemanticReview(
            approved=approved, rationale="Scripted model judgment.",
            concerns=[] if approved else ["The implementation is incomplete."],
        ) for approved in approvals
    )
    monkeypatch.setattr(SyntaxValidator, "review_repair", lambda *args, **kwargs: next(results))


def test_apply_plan_tool_repairs_syntax_invalid_csharp_generation(monkeypatch) -> None:
    _mock_reviews(monkeypatch, False, True)
    registry = _build_registry(_FakeLlmInvalidThenRepair)
    tool = ApplyPlanSweCodeChangeTool(registry)
    original = "public class Example { public void Run() { } }\n"

    result = tool.execute(
        swe_context=_build_swe_context(),
        original_code=original,
        target_file="src/Example.cs",
    )

    assert 'Console.WriteLine("updated")' in result["generated_code"]
    assert result["used_fallback_to_original"] is False
    assert result["syntax_validation"]["final"]["valid"] is True
    assert result["syntax_validation"]["rejected_invalid_generation"] is False
    assert len(result["syntax_validation"]["repair_attempts"]) == 1
    assert _FakeLlmInvalidThenRepair.last_instance.calls == 2


def test_apply_plan_tool_rejects_csharp_that_remains_syntax_invalid(monkeypatch) -> None:
    _mock_reviews(monkeypatch, False, False, False)
    registry = _build_registry(_FakeLlmAlwaysInvalid)
    tool = ApplyPlanSweCodeChangeTool(registry)
    original = "public class Example { public void Run() { } }\n"

    result = tool.execute(
        swe_context=_build_swe_context(),
        original_code=original,
        target_file="src/Example.cs",
    )

    assert result["generated_code"] == original
    assert result["used_fallback_to_original"] is True
    assert result["syntax_validation"]["rejected_invalid_generation"] is True
    assert len(result["syntax_validation"]["repair_attempts"]) == 2
    assert "LLM review rejected" in result["error"]
    assert result["apply_outcome"] == "syntax_rejected_fallback"


def test_parser_error_count_does_not_override_model_generation_review(monkeypatch):
    _mock_reviews(monkeypatch, True)
    result = ApplyPlanSweCodeChangeTool(_build_registry(_FakeLlmAlwaysInvalid)).execute(
        swe_context=_build_swe_context(),
        original_code="public class Example { public void Run() {} }",
        target_file="src/Example.cs",
    )
    assert result["syntax_validation"]["final"]["valid"] is False
    assert result["syntax_validation"]["final_semantic_review"]["approved"] is True
    assert result["syntax_validation"]["repair_attempts"] == []
    assert result["syntax_validation"]["rejected_invalid_generation"] is False


class _FakeLlmNoOp:
    def chat(self, prompt: str, **kwargs: object) -> str:
        return "No change is required.\n\n```python\nprint('old')\n```"


class _FakeLlmEmpty:
    def chat(self, prompt: str, **kwargs: object) -> str:
        return "   "


def test_apply_plan_tool_distinguishes_model_no_op_from_fallback() -> None:
    registry = _build_registry(_FakeLlmNoOp)
    tool = ApplyPlanSweCodeChangeTool(registry)
    original = "print('old')"

    result = tool.execute(
        swe_context=_build_swe_context(),
        original_code=original,
        target_file="src/file.py",
    )

    assert result["generated_code"].strip() == original
    assert result["used_fallback_to_original"] is True
    assert result["apply_outcome"] == "unchanged_model_output"
    assert result["empty_generated_guardrail_triggered"] is False
    assert result["error"] is None


def test_apply_plan_tool_flags_empty_response_fallback() -> None:
    registry = _build_registry(_FakeLlmEmpty)
    tool = ApplyPlanSweCodeChangeTool(registry)
    original = "print('old')"

    result = tool.execute(
        swe_context=_build_swe_context(),
        original_code=original,
        target_file="src/file.py",
    )

    assert result["generated_code"] == original
    assert result["used_fallback_to_original"] is True
    assert result["empty_generated_guardrail_triggered"] is False
    assert result["apply_outcome"] == "empty_response_fallback"


def test_apply_plan_tool_flags_documentation_guardrail_block() -> None:
    registry = _build_registry(_FakeLlmSuccess)
    tool = ApplyPlanSweCodeChangeTool(registry)

    result = tool.execute(
        swe_context=_build_swe_context(),
        original_code="# docs",
        target_file="docs/readme.md",
    )

    assert result["guardrail_blocked"] is True
    assert result["apply_outcome"] == "guardrail_blocked"


def test_apply_plan_tool_classifier_prioritizes_infrastructure_states() -> None:
    classify = ApplyPlanSweCodeChangeTool._classify_apply_outcome

    assert (
        classify(
            original_code="a",
            generated_code="b",
            empty_generated_guardrail_triggered=False,
            syntax_rejected=False,
            generation_error=False,
            guardrail_blocked=False,
        )
        == "modified"
    )
    assert (
        classify(
            original_code="a",
            generated_code="a",
            empty_generated_guardrail_triggered=False,
            syntax_rejected=False,
            generation_error=True,
            guardrail_blocked=False,
        )
        == "generation_error_fallback"
    )


class _FakeExplanationService:
    def __init__(self, kb, config):
        self.kb = kb
        self.config = config

    def explain_change(self, swe_context, original_code, modified_code):
        return SweCodeChangeExplanation(
            plan=swe_context.plan,
            overall_verdict="acceptable",
            confidence=0.9,
            rationale="Looks good",
            nfr_impacts=[],
            risks=[],
            recommended_tests=["run tests"],
        )


def test_judge_tool_uses_injected_explanation_service() -> None:
    execution_cfg = SimpleNamespace(
        max_summary_chars=200,
        max_security_context_chars=120,
        max_single_shot_code_chars=12000,
        chunk_lines=3,
    )
    cfg = SimpleNamespace(execution=execution_cfg)
    ctx = SimpleNamespace(config=cfg, kb="kb")
    registry = SimpleNamespace(
        _create_swe_server_context=lambda: ctx,
        _explanation_service_cls=_FakeExplanationService,
    )

    tool = JudgeSweCodeChangeTool(registry)
    explanation = tool.execute(
        swe_context=_build_swe_context(),
        original_code="print('old')",
        modified_code="print('new')",
    )

    assert explanation.overall_verdict == "acceptable"
    assert explanation.rationale == "Looks good"
