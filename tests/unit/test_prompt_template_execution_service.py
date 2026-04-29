import logging

from src.service.prompt_data_mapping_service import PromptDataMappingService
from src.service.prompt_template_execution_service import PromptTemplateExecutionService


def _make_service() -> PromptTemplateExecutionService:
    return PromptTemplateExecutionService(logger=logging.getLogger("test"))


def _template_item(name: str, content: str) -> dict:
    return {"kind": "swe_concern_template", "name": name, "content": content}


def _data_item(payload: dict) -> dict:
    import json

    return {"kind": "swe_concern_data", "content": json.dumps(payload)}


# ---------------------------------------------------------------------------
# render_prompt_context
# ---------------------------------------------------------------------------


def test_render_prompt_context_includes_swe_summary():
    service = _make_service()
    result = service.render_prompt_context("my summary", [], None)
    assert "my summary" in result


def test_render_prompt_context_includes_security_context_when_provided():
    service = _make_service()
    result = service.render_prompt_context("summary", [], "extra security info")
    assert "Security Extra Context" in result
    assert "extra security info" in result


def test_render_prompt_context_omits_security_section_when_none():
    service = _make_service()
    result = service.render_prompt_context("summary", [], None)
    assert "Security Extra Context" not in result


def test_render_prompt_context_lists_all_template_names():
    service = _make_service()
    templates = [
        {"name": "base_template", "content": "# base"},
        {"concern_group": "reliability", "content": "# reliability"},
    ]
    result = service.render_prompt_context("summary", templates, None)
    assert "base_template" in result
    assert "reliability" in result


# ---------------------------------------------------------------------------
# build_executed_prompts – double-brace placeholders
# ---------------------------------------------------------------------------


def test_build_executed_prompts_resolves_double_brace_placeholders():
    service = _make_service()
    templates = [
        _data_item({"LANGUAGE": "Python"}),
        _template_item("base", "Write code in {{LANGUAGE}}"),
    ]
    result = service.build_executed_prompts(templates)
    assert len(result) == 1
    assert "Python" in result[0]["content"]


def test_build_executed_prompts_skips_template_with_missing_placeholder():
    service = _make_service()
    templates = [
        _template_item("base", "Write code in {{MISSING_KEY}}"),
    ]
    result = service.build_executed_prompts(templates)
    assert result == []


def test_build_executed_prompts_ignores_non_template_items():
    service = _make_service()
    templates = [
        _data_item({"X": "y"}),
    ]
    result = service.build_executed_prompts(templates)
    assert result == []


def test_build_executed_prompts_skips_test_base_template_when_no_unit_test_example():
    service = _make_service()
    templates = [
        _data_item({"LANGUAGE": "Python"}),
        _template_item("test_base_template", "Write tests for {{LANGUAGE}}"),
    ]
    result = service.build_executed_prompts(templates)
    assert result == []


def test_build_executed_prompts_includes_test_base_template_when_unit_test_example_present():
    service = _make_service()
    templates = [
        _data_item({"LANGUAGE": "Python", "UNIT_TEST_EXAMPLE": "def test_foo(): pass"}),
        _template_item("test_base_template", "Write tests for {{LANGUAGE}}"),
    ]
    result = service.build_executed_prompts(templates)
    assert len(result) == 1
    assert result[0]["name"] == "test_base_template"


# ---------------------------------------------------------------------------
# build_executed_prompts – single-brace example substitution
# ---------------------------------------------------------------------------


def test_build_executed_prompts_substitutes_single_brace_code_example():
    service = _make_service()
    templates = [
        _data_item({"CODE_EXAMPLE": "def my_func(): pass"}),
        _template_item("base", "Use this: {CODE_EXAMPLE}"),
    ]
    result = service.build_executed_prompts(templates)
    assert "def my_func(): pass" in result[0]["content"]


def test_build_executed_prompts_substitutes_code_example_with_space_in_token():
    service = _make_service()
    templates = [
        _data_item({"CODE_EXAMPLE": "def hello(): pass"}),
        _template_item("base", "Use this: {CODE EXAMPLE}"),
    ]
    result = service.build_executed_prompts(templates)
    assert "def hello(): pass" in result[0]["content"]


def test_build_executed_prompts_does_not_replace_single_brace_when_value_is_empty():
    service = _make_service()
    templates = [
        _data_item({}),
        _template_item("base", "Use this: {CODE_EXAMPLE}"),
    ]
    result = service.build_executed_prompts(templates)
    # Template renders (no double-brace placeholders → no missing), but token stays unreplaced
    assert "{CODE_EXAMPLE}" in result[0]["content"]


# ---------------------------------------------------------------------------
# _apply_optional_markdown_rules
# ---------------------------------------------------------------------------


def test_apply_optional_markdown_rules_removes_example_section_when_no_code():
    service = _make_service()
    content = "## Intro\n\n### Example 1:\nSome code here\n\n## Notes\nDone\n"
    result = service._apply_optional_markdown_rules(
        template_name="base",
        rendered=content,
        has_code_example=False,
        has_unit_test_example=True,
    )
    assert "Example 1:" not in result
    assert "Notes" in result


def test_apply_optional_markdown_rules_keeps_example_section_when_code_present():
    service = _make_service()
    content = "## Intro\n\n### Example 1:\nSome code\n\n## Notes\nDone\n"
    result = service._apply_optional_markdown_rules(
        template_name="base",
        rendered=content,
        has_code_example=True,
        has_unit_test_example=True,
    )
    assert "Example 1:" in result


def test_apply_optional_markdown_rules_removes_unit_tests_section_when_no_example():
    service = _make_service()
    content = "## Main\n\n## Unit Tests:\ntest stuff\n"
    result = service._apply_optional_markdown_rules(
        template_name="base",
        rendered=content,
        has_code_example=True,
        has_unit_test_example=False,
    )
    assert "Unit Tests:" not in result


# ---------------------------------------------------------------------------
# _render_template_content – edge cases
# ---------------------------------------------------------------------------


def test_render_template_content_no_placeholders_returns_content_unchanged():
    service = _make_service()
    content = "No placeholders here."
    rendered, missing = service._render_template_content(content, {})
    assert rendered == content
    assert missing == []


def test_render_template_content_returns_missing_keys():
    service = _make_service()
    content = "Use {{MISSING}}"
    rendered, missing = service._render_template_content(content, {})
    assert "MISSING" in missing


def test_render_template_content_replaces_multiple_distinct_placeholders():
    service = _make_service()
    content = "{{A}} and {{B}}"
    rendered, missing = service._render_template_content(
        content, {"A": "alpha", "B": "beta"}
    )
    assert rendered == "alpha and beta"
    assert missing == []
