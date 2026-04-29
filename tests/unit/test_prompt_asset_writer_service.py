import json
import os
from datetime import datetime
from pathlib import Path

from src.models.code_gen_plan import CodeGenPlan
from src.service.prompt_asset_writer_service import PromptAssetWriterService


def _fixed_now() -> datetime:
    return datetime(2026, 1, 15, 10, 30, 0)


def _make_service() -> PromptAssetWriterService:
    return PromptAssetWriterService(now_provider=_fixed_now)


def _make_plan(description: str = "Improve reliability") -> CodeGenPlan:
    return CodeGenPlan(
        problem_description=description,
        high_level_steps=["Step 1"],
    )


# ---------------------------------------------------------------------------
# persist_generated_prompt_assets – folder creation and file presence
# ---------------------------------------------------------------------------


def test_persist_creates_run_folder_under_output_root(tmp_path):
    service = _make_service()
    plan = _make_plan()

    run_folder = service.persist_generated_prompt_assets(
        repo_root=str(tmp_path),
        output_folder="out",
        plan=plan,
        swe_summary="summary",
        templates=[],
        security_extra_context=None,
        prompt_context="context",
    )

    assert Path(run_folder).exists()
    assert Path(run_folder).parent == tmp_path / "out"


def test_persist_writes_plan_json(tmp_path):
    service = _make_service()
    plan = _make_plan("Fix auth")

    run_folder = service.persist_generated_prompt_assets(
        repo_root=str(tmp_path),
        output_folder="out",
        plan=plan,
        swe_summary="summary",
        templates=[],
        security_extra_context=None,
        prompt_context="context",
    )

    plan_file = Path(run_folder) / "plan.json"
    assert plan_file.exists()
    payload = json.loads(plan_file.read_text())
    assert payload["problem_description"] == "Fix auth"


def test_persist_writes_swe_summary_md(tmp_path):
    service = _make_service()

    run_folder = service.persist_generated_prompt_assets(
        repo_root=str(tmp_path),
        output_folder="out",
        plan=_make_plan(),
        swe_summary="This is the SWE summary.",
        templates=[],
        security_extra_context=None,
        prompt_context="context",
    )

    summary_file = Path(run_folder) / "swe_summary.md"
    assert summary_file.exists()
    assert "This is the SWE summary." in summary_file.read_text()


def test_persist_writes_prompt_context_md(tmp_path):
    service = _make_service()

    run_folder = service.persist_generated_prompt_assets(
        repo_root=str(tmp_path),
        output_folder="out",
        plan=_make_plan(),
        swe_summary="summary",
        templates=[],
        security_extra_context=None,
        prompt_context="## Prompt Context\nSome details here.",
    )

    context_file = Path(run_folder) / "prompt_context.md"
    assert context_file.exists()
    assert "Some details here." in context_file.read_text()


def test_persist_writes_executed_prompts_file(tmp_path):
    service = _make_service()
    executed = [{"name": "base_template", "content": "Do the work"}]

    run_folder = service.persist_generated_prompt_assets(
        repo_root=str(tmp_path),
        output_folder="out",
        plan=_make_plan(),
        swe_summary="summary",
        templates=[],
        security_extra_context=None,
        prompt_context="context",
        executed_prompts=executed,
    )

    executed_file = Path(run_folder) / "executed_prompts.md"
    assert executed_file.exists()
    content = executed_file.read_text()
    assert "base_template" in content
    assert "Do the work" in content


def test_persist_writes_templates_subfolder_from_executed_prompts(tmp_path):
    service = _make_service()
    executed = [
        {"name": "base_template", "content": "prompt one"},
        {"name": "test_base_template", "content": "prompt two"},
    ]

    run_folder = service.persist_generated_prompt_assets(
        repo_root=str(tmp_path),
        output_folder="out",
        plan=_make_plan(),
        swe_summary="summary",
        templates=[],
        security_extra_context=None,
        prompt_context="context",
        executed_prompts=executed,
    )

    templates_dir = Path(run_folder) / "templates"
    files = sorted(templates_dir.iterdir())
    assert len(files) == 2
    assert files[0].name.startswith("01-")
    assert files[1].name.startswith("02-")


def test_persist_uses_absolute_output_folder_directly(tmp_path):
    service = _make_service()
    absolute_out = tmp_path / "absolute_out"

    run_folder = service.persist_generated_prompt_assets(
        repo_root="/ignored/repo/root",
        output_folder=str(absolute_out),
        plan=_make_plan(),
        swe_summary="summary",
        templates=[],
        security_extra_context=None,
        prompt_context="context",
    )

    assert Path(run_folder).parent == absolute_out


# ---------------------------------------------------------------------------
# _slugify_for_filename
# ---------------------------------------------------------------------------


def test_slugify_replaces_spaces_and_special_chars():
    result = PromptAssetWriterService._slugify_for_filename("Improve: reliability & resiliency!")
    assert " " not in result
    assert ":" not in result
    assert "&" not in result
    assert "!" not in result


def test_slugify_truncates_to_48_chars():
    long_text = "a" * 100
    result = PromptAssetWriterService._slugify_for_filename(long_text)
    assert len(result) <= 48


def test_slugify_returns_prompt_for_empty_string():
    result = PromptAssetWriterService._slugify_for_filename("")
    assert result == "prompt"


def test_slugify_lowercases_output():
    result = PromptAssetWriterService._slugify_for_filename("MixedCaseInput")
    assert result == result.lower()


# ---------------------------------------------------------------------------
# _build_run_folder – timestamp prefix
# ---------------------------------------------------------------------------


def test_build_run_folder_uses_now_provider_timestamp(tmp_path):
    service = _make_service()
    run_folder = service._build_run_folder(str(tmp_path), "my task")
    folder_name = os.path.basename(run_folder)
    assert folder_name.startswith("20260115T103000Z")
