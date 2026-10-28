import json

import pytest

from src.service.syntax_validator import SyntaxValidator


def test_csharp_syntax_validator_accepts_valid_source() -> None:
    result = SyntaxValidator().validate(
        "src/Example.cs",
        "public class Example { public void Run() { } }\n",
    )

    assert result.available is True
    assert result.valid is True
    assert result.diagnostics == []


def test_csharp_syntax_validator_reports_invalid_source_location() -> None:
    result = SyntaxValidator().validate(
        "src/Example.cs",
        "public class Example {\n    public void Run( {\n}\n",
    )

    assert result.available is True
    assert result.valid is False
    assert result.diagnostics
    assert result.diagnostics[0].start_line >= 1


def test_syntax_validator_is_explicit_when_parser_is_unavailable() -> None:
    result = SyntaxValidator().validate("src/file.unknown", "not source")

    assert result.available is False
    assert result.valid is True


def test_transport_bom_does_not_produce_spurious_diagnostics() -> None:
    validator = SyntaxValidator()
    body = "//-- header\nclass A { void M() { } }\n"

    for prefix in ("", "\ufeff", "ï»¿"):
        result = validator.validate("a.cs", prefix + body)

        assert result.valid is True, prefix
        assert result.diagnostics == [], prefix


def test_transport_bom_does_not_mask_real_errors() -> None:
    result = SyntaxValidator().validate(
        "a.cs",
        "ï»¿//-- header\npublic class A {\n    public void M( {\n}\n",
    )

    assert result.valid is False
    assert result.diagnostics


class _ReviewLlm:
    def __init__(self, approved):
        self.approved = approved
        self.prompts = []

    def chat(self, prompt):
        self.prompts.append(prompt)
        return json.dumps(
            {
                "approved": self.approved,
                "rationale": "Scripted semantic decision.",
                "concerns": []
                if self.approved
                else ["Proposed implementation bypasses the requirement."],
            }
        )


@pytest.mark.parametrize(
    "target,proposed",
    [
        ("C.cs", "#nullable disable\nclass C {}"),
        (
            "Generator.cs",
            'class Generator { void Emit() { sb.Append($"return {name}!;"); } }',
        ),
        ("module.py", "def encode(value):\n    return fallback_serializer(value)\n"),
    ],
)
def test_repair_semantics_are_delegated_with_source_intent_and_diagnostics(
    target, proposed
):
    client = _ReviewLlm(False)
    diagnostics = [{"message": "Native collection encoding is missing."}]
    review = SyntaxValidator(client).review_repair(
        target,
        "original implementation",
        proposed,
        problem_summary="Implement native encoding without serializer delegation.",
        diagnostics=diagnostics,
    )
    assert review.approved is False
    payload = json.loads(client.prompts[0].split("\nInput data:", 1)[1])
    assert payload["current_source"] == "original implementation"
    assert payload["proposed_source"] == proposed
    assert payload["target_file"] == target
    assert payload["verification_diagnostics"] == diagnostics
    assert "without serializer delegation" in payload["issue_intent_and_nfrs"]


def test_semantic_review_uses_model_verdict_not_csharp_regexes_or_parser(monkeypatch):
    client = _ReviewLlm(True)
    validator = SyntaxValidator(client)
    monkeypatch.setattr(validator._extractor, "_create_parser", lambda suffix: None)
    review = validator.review_repair(
        "Generator.cs", "original", 'sb.AppendLine("Hello!");'
    )
    assert review.approved is True
    assert len(client.prompts) == 1
