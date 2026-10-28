import json

import pytest
from pydantic import ValidationError

from src.models.utility_decisions import DiagnosticSymbols, SemanticReview
from src.service.tool_prompt_template_service import ToolPromptTemplateError
from src.service.utility_llm_service import MAX_RESPONSE_CORRECTIONS, UtilityLlmService


class ScriptedClient:
    def __init__(self, response):
        self.response = response
        self.prompts = []

    def chat(self, prompt):
        self.prompts.append(prompt)
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def test_custom_utility_root_renders_schema_and_preserves_input_placeholders(tmp_path):
    directory = tmp_path / "utils"
    directory.mkdir()
    (directory / "review.md").write_text(
        "schema={{ SCHEMA }}\ninput={{ INPUT_JSON }}", encoding="utf-8"
    )
    client = ScriptedClient(
        '{"approved": true, "rationale": "Grounded.", "concerns": []}'
    )
    result = UtilityLlmService(client, tmp_path).complete(
        "review", SemanticReview, {"source": "{{ UNTRUSTED }}"}
    )
    assert result.approved is True
    assert '"additionalProperties": false' in client.prompts[0]
    assert "{{ UNTRUSTED }}" in client.prompts[0]


@pytest.mark.parametrize(
    "response",
    [
        "not JSON",
        '{"approved": "true", "rationale": "Coerced.", "concerns": []}',
        '{"approved": true, "rationale": "Conflicting.", "concerns": ["Missing implementation."]}',
        '{"approved": false, "rationale": "Unexplained.", "concerns": []}',
        '{"approved": true, "rationale": "Unexpected field.", "concerns": [], "extra": 1}',
        '{"approved": true, "rationale": "  ", "concerns": []}',
    ],
)
def test_invalid_decisions_fail_explicitly_without_a_fallback(response, caplog):
    client = ScriptedClient(response)
    with pytest.raises(ValidationError):
        UtilityLlmService(client).complete("repair_review", SemanticReview, {})
    assert len(client.prompts) == 2
    assert "requesting one model correction" in caplog.text
    assert "no heuristic fallback" in caplog.text


def test_model_failure_is_propagated_and_logged(caplog):
    client = ScriptedClient(RuntimeError("Model unavailable"))
    with pytest.raises(RuntimeError, match="Model unavailable"):
        UtilityLlmService(client).complete("repair_review", SemanticReview, {})
    assert len(client.prompts) == 1
    assert "Model unavailable" in caplog.text


def test_missing_utility_template_does_not_call_the_model(tmp_path):
    client = ScriptedClient("{}")
    with pytest.raises(ToolPromptTemplateError):
        UtilityLlmService(client, tmp_path).complete("absent", SemanticReview, {})
    assert client.prompts == []


def test_missing_placeholder_fails_before_model_call(tmp_path):
    (tmp_path / "utils").mkdir()
    (tmp_path / "utils" / "bad.md").write_text("{{ UNKNOWN }}", encoding="utf-8")
    client = ScriptedClient("{}")
    with pytest.raises(ToolPromptTemplateError, match="UNKNOWN"):
        UtilityLlmService(client, tmp_path).complete("bad", SemanticReview, {})
    assert client.prompts == []


@pytest.mark.parametrize("symbols", [[""], [" "], [1]])
def test_symbol_response_rejects_empty_or_coerced_names(symbols):
    with pytest.raises(ValidationError):
        DiagnosticSymbols.model_validate_json(json.dumps({"symbols": symbols}))


@pytest.mark.parametrize(
    "template",
    [
        "repair_review",
        "issue_understanding",
        "implementation_plan_review",
        "diagnostic_symbols",
        "symbol_context_selection",
        "implementation_plan",
        "implementation_plan_correction",
        "high_level_plan",
        "structured_response_correction",
    ],
)
def test_packaged_utility_prompts_render_from_requested_directory(template):
    prompt = UtilityLlmService().render(template, {"sample": True}, SemanticReview)
    assert "{{ SCHEMA }}" not in prompt
    assert "{{ INPUT_JSON }}" not in prompt
    assert '"sample": true' in prompt


@pytest.mark.parametrize("approved", [True, False])
def test_invalid_review_is_corrected_by_model_without_coercing_verdict(approved):
    class CorrectingClient:
        def __init__(self):
            self.prompts = []

        def chat(self, prompt):
            self.prompts.append(prompt)
            if len(self.prompts) == 1:
                return '{"approved": true, "rationale": "Contradictory.", "concerns": ["Missing behavior."]}'
            return json.dumps(
                {
                    "approved": approved,
                    "rationale": "Evidence reconsidered.",
                    "concerns": []
                    if approved
                    else ["The required behavior is still missing."],
                }
            )

    client = CorrectingClient()
    result = UtilityLlmService(client).complete(
        "implementation_plan_review",
        SemanticReview,
        {"requirement": "Native collections."},
    )
    assert result.approved is approved
    assert len(client.prompts) == 2
    assert "Native collections." in client.prompts[1]
    assert "Approval requires no concerns" in client.prompts[1]


@pytest.mark.parametrize("template", ["repair_review", "structured_response_correction"])
def test_invalid_correction_never_recurses_or_exceeds_explicit_limit(template):
    client = ScriptedClient("not JSON")
    with pytest.raises(ValidationError):
        UtilityLlmService(client).complete(template, SemanticReview, {})
    assert MAX_RESPONSE_CORRECTIONS == 1
    assert len(client.prompts) == 1 + MAX_RESPONSE_CORRECTIONS
