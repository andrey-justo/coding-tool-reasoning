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
