from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from src.mcp.tools.repair_test_failure_tool import RepairTestFailureTool

INCOMPLETE_GENERATOR = """public class AkkaSerializerGenerator
{
    public bool IsSupported(ITypeSymbol type) => type.SpecialType != SpecialType.None;
}
"""

FIXED_GENERATOR = """public class AkkaSerializerGenerator
{
    public bool IsSupported(ITypeSymbol type) =>
        type is IArrayTypeSymbol || type.SpecialType != SpecialType.None;
}
"""

SPEC_FILE = """public class AkkaSerializerGeneratorDiagnosticsSpec
{
    public void Should_not_report_AKKASG011_for_arrays() => Assert.Empty(Diagnostics);
}
"""

_STACK = (
    "   at AkkaSerializerGeneratorDiagnosticsSpec.Should_not_report_AKKASG011_for_arrays() "
    "in C:\\gate\\src\\core\\Akka.Serialization.V2.Tests\\"
    "AkkaSerializerGeneratorDiagnosticsSpec.cs:line 3"
)

TRX_DOCUMENT = f"""<?xml version="1.0" encoding="utf-8"?>
<TestRun xmlns="http://microsoft.com/schemas/VisualStudio/TeamTest/2010">
  <Results>
    <UnitTestResult testName="Spec.Should_not_report_AKKASG011_for_arrays" outcome="Failed">
      <Output>
        <ErrorInfo>
          <Message>AKKASG011 was reported for int[].</Message>
          <StackTrace>{_STACK}</StackTrace>
        </ErrorInfo>
      </Output>
    </UnitTestResult>
  </Results>
</TestRun>
"""

GENERATOR_PATH = "src/core/Akka.Serialization.V2.Generators/AkkaSerializerGenerator.cs"
SPEC_PATH = (
    "src/core/Akka.Serialization.V2.Tests/AkkaSerializerGeneratorDiagnosticsSpec.cs"
)


class _FakeLlm:
    last_instance = None

    response = "```csharp\n" + FIXED_GENERATOR + "```"

    def __init__(self) -> None:
        self.prompts: list[str] = []
        type(self).last_instance = self

    def chat(self, prompt: str, **kwargs) -> str:
        self.prompts.append(prompt)
        return self.response


class _InvalidSyntaxLlm(_FakeLlm):
    response = "```csharp\npublic class Example { public void Run( { }\n```"


class _UnchangedLlm(_FakeLlm):
    response = "```csharp\n" + INCOMPLETE_GENERATOR + "```"


def _build_registry(llm_cls, *, max_repair_files: int = 1):
    execution_cfg = SimpleNamespace(
        max_test_failures=10,
        max_test_output_chars=6000,
        max_test_ast_locations=5,
        max_test_repair_files=max_repair_files,
        max_test_related_declarations=40,
        max_syntax_diagnostics=20,
    )
    verification_cfg = SimpleNamespace(project_type="dotnet")
    ctx = SimpleNamespace(
        config=SimpleNamespace(execution=execution_cfg, verification=verification_cfg)
    )
    return SimpleNamespace(
        _llm_client_cls=llm_cls,
        _create_swe_server_context=lambda: ctx,
        _logger=SimpleNamespace(warning=lambda *args, **kwargs: None),
    )


def _write_trx(tmp_path: Path) -> str:
    results_path = tmp_path / "results.trx"
    results_path.write_text(TRX_DOCUMENT, encoding="utf-8")
    return str(results_path)


def test_repair_targets_production_file_when_failure_is_in_a_spec(
    tmp_path: Path,
) -> None:
    tool = RepairTestFailureTool(_build_registry(_FakeLlm))

    result = tool.execute(
        problem_summary="Collections must not raise AKKASG011.",
        test_output="Failed Spec.Should_not_report_AKKASG011_for_arrays",
        generated_code_by_file={
            GENERATOR_PATH: INCOMPLETE_GENERATOR,
            SPEC_PATH: SPEC_FILE,
        },
        results_path=_write_trx(tmp_path),
        test_command=["dotnet", "test"],
    )

    assert result["failures_parser"] == "trx"
    # The stack trace points at the spec, but rewriting a spec to make it pass
    # would hide the defect, so production code is repaired first.
    assert result["repair_targets"] == [GENERATOR_PATH]
    assert result["repaired_files"] == [GENERATOR_PATH]
    assert result["changed"] is True
    assert result["generated_code_by_file"][SPEC_PATH] == SPEC_FILE

    prompt = _FakeLlm.last_instance.prompts[0]
    assert "AKKASG011 was reported for int[]." in prompt
    assert "Collections must not raise AKKASG011." in prompt
    assert "dotnet test" in prompt
    assert "AkkaSerializerGeneratorDiagnosticsSpec" in prompt

    file_result = result["file_results"][0]
    assert file_result["matched_by_stack_trace"] is False
    assert file_result["related_files"] == [SPEC_PATH]


def test_repair_rejects_syntactically_invalid_output(tmp_path: Path) -> None:
    tool = RepairTestFailureTool(_build_registry(_InvalidSyntaxLlm))

    result = tool.execute(
        problem_summary="summary",
        test_output="failed",
        generated_code_by_file={GENERATOR_PATH: INCOMPLETE_GENERATOR},
        results_path=_write_trx(tmp_path),
    )

    assert result["changed"] is False
    assert result["generated_code_by_file"][GENERATOR_PATH] == INCOMPLETE_GENERATOR
    assert "invalid syntax" in result["file_results"][0]["rejected_reason"]


def test_repair_rejects_unchanged_output(tmp_path: Path) -> None:
    tool = RepairTestFailureTool(_build_registry(_UnchangedLlm))

    result = tool.execute(
        problem_summary="summary",
        test_output="failed",
        generated_code_by_file={GENERATOR_PATH: INCOMPLETE_GENERATOR},
        results_path=_write_trx(tmp_path),
    )

    assert result["changed"] is False
    assert "unchanged" in result["file_results"][0]["rejected_reason"]


def test_repair_reports_error_when_no_failure_can_be_parsed() -> None:
    tool = RepairTestFailureTool(_build_registry(_FakeLlm))

    result = tool.execute(
        problem_summary="summary",
        test_output="   ",
        generated_code_by_file={GENERATOR_PATH: INCOMPLETE_GENERATOR},
    )

    assert result["changed"] is False
    assert result["repaired_files"] == []
    assert result["error"]


def test_repair_limits_the_number_of_files_per_round(tmp_path: Path) -> None:
    tool = RepairTestFailureTool(_build_registry(_FakeLlm, max_repair_files=2))

    result = tool.execute(
        problem_summary="summary",
        test_output="failed",
        generated_code_by_file={
            GENERATOR_PATH: INCOMPLETE_GENERATOR,
            "src/core/Other.cs": INCOMPLETE_GENERATOR,
            "src/core/Another.cs": INCOMPLETE_GENERATOR,
            SPEC_PATH: SPEC_FILE,
        },
        results_path=_write_trx(tmp_path),
    )

    assert len(result["repair_targets"]) == 2
