from __future__ import annotations

from types import SimpleNamespace

from src.mcp.tools.apply_plan_swe_code_change_tool import ApplyPlanSweCodeChangeTool
from src.mcp.tools.repair_build_failure_tool import RepairBuildFailureTool

BROKEN_CSHARP = """public class Example
{
    private string Name(INamedTypeSymbol symbol) => symbol.Name;

    public string Render(ITypeSymbol target) => Name(target!);
}
"""

FIXED_CSHARP = """public class Example
{
    private string Name(INamedTypeSymbol symbol) => symbol.Name;

    public string Render(INamedTypeSymbol target) => Name(target);
}
"""

BUILD_OUTPUT = (
    "C:\\Temp\\gate\\src/Example.cs(5,52): error CS1503: Argument 1: cannot convert "
    "from 'ITypeSymbol' to 'INamedTypeSymbol' [C:\\Temp\\gate\\src\\App.csproj]"
)


class _FakeLlm:
    last_instance = None

    response = "```csharp\n" + FIXED_CSHARP + "```"

    def __init__(self) -> None:
        self.prompts: list[str] = []
        type(self).last_instance = self

    def chat(self, prompt: str, **kwargs) -> str:
        self.prompts.append(prompt)
        return self.response


class _InvalidSyntaxLlm(_FakeLlm):
    response = "```csharp\npublic class Example { public void Run( { }\n```"


class _UnchangedLlm(_FakeLlm):
    response = "```csharp\n" + BROKEN_CSHARP + "```"


class _ChunkRepairLlm(_FakeLlm):
    def chat(self, prompt: str, **kwargs) -> str:
        self.prompts.append(prompt)
        chunk_section = prompt.split("=== Current complete chunk", 1)[1]
        current_chunk = chunk_section.split("```\n", 1)[1].rsplit("\n```", 1)[0]
        repaired_chunk = current_chunk.replace("WrongType", "RightType")
        return f"```csharp\n{repaired_chunk}\n```"


class _DestructiveChunkLlm(_FakeLlm):
    response = "```csharp\npublic string RightType => \"fixed\";\n```"


class _EchoLlm(_FakeLlm):
    """Return the file unchanged, as a model that refuses to edit a target does."""

    def chat(self, prompt: str, **kwargs) -> str:
        self.prompts.append(prompt)
        section = prompt.split("=== Current file content that fails to compile", 1)[1]
        current = section.split("```\n", 1)[1].rsplit("\n```", 1)[0]
        return f"```csharp\n{current}\n```"

def _build_registry(
    llm_cls,
    *,
    max_single_shot_code_chars: int = 12000,
    chunk_lines: int = 160,
    max_build_repair_chunks: int = 4,
):
    execution_cfg = SimpleNamespace(
        max_build_diagnostics=20,
        max_build_output_chars=6000,
        max_build_ast_locations=5,
        max_syntax_diagnostics=20,
        max_single_shot_code_chars=max_single_shot_code_chars,
        chunk_lines=chunk_lines,
        max_build_repair_chunks=max_build_repair_chunks,
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


def test_repair_applies_fix_and_reports_diagnostics() -> None:
    tool = RepairBuildFailureTool(_build_registry(_FakeLlm))
    repair_history = [
        {
            "attempt": attempt,
            "build_status_before": "fail",
            "build_status_after": "fail",
            "diagnostics_by_file": {"src/Example.cs": [{"code": "CS1503"}]},
        }
        for attempt in range(1, 8)
    ]

    result = tool.execute(
        problem_summary="Serializer must accept named type symbols.",
        build_output=BUILD_OUTPUT,
        generated_code_by_file={"src/Example.cs": BROKEN_CSHARP},
        build_command=["dotnet", "build"],
        attempt=1,
        max_attempts=10,
        repair_history=repair_history,
    )

    assert result["changed"] is True
    assert result["repaired_files"] == ["src/Example.cs"]
    assert result["generated_code_by_file"]["src/Example.cs"].strip() == (
        FIXED_CSHARP.strip()
    )
    assert result["diagnostics_by_file"]["src/Example.cs"][0]["code"] == "CS1503"
    assert result["unmatched_diagnostics"] == []

    prompt = _FakeLlm.last_instance.prompts[0]
    assert "CS1503" in prompt
    assert "Serializer must accept named type symbols." in prompt
    assert "dotnet build" in prompt
    assert '"attempt": 3' in prompt
    assert '"attempt": 2' not in prompt
    assert result["file_results"][0]["ast_context_available"] is True
    assert result["repair_history_size"] == 5


def test_repair_rejects_syntactically_invalid_output() -> None:
    tool = RepairBuildFailureTool(_build_registry(_InvalidSyntaxLlm))

    result = tool.execute(
        problem_summary="summary",
        build_output=BUILD_OUTPUT,
        generated_code_by_file={"src/Example.cs": BROKEN_CSHARP},
    )

    assert result["changed"] is False
    assert result["generated_code_by_file"]["src/Example.cs"] == BROKEN_CSHARP
    assert "invalid syntax" in result["file_results"][0]["rejected_reason"]


def test_repair_rejects_unchanged_output() -> None:
    tool = RepairBuildFailureTool(_build_registry(_UnchangedLlm))

    result = tool.execute(
        problem_summary="summary",
        build_output=BUILD_OUTPUT,
        generated_code_by_file={"src/Example.cs": BROKEN_CSHARP},
    )

    assert result["changed"] is False
    assert "unchanged" in result["file_results"][0]["rejected_reason"]


def test_repair_reports_error_when_no_diagnostic_matches_generated_files() -> None:
    tool = RepairBuildFailureTool(_build_registry(_FakeLlm))

    result = tool.execute(
        problem_summary="summary",
        build_output="src/Unrelated.cs(1,1): error CS0103: missing [a.csproj]",
        generated_code_by_file={"src/Example.cs": BROKEN_CSHARP},
    )

    assert result["changed"] is False
    assert result["repaired_files"] == []
    assert result["error"]
    assert len(result["unmatched_diagnostics"]) == 1


def test_repair_prioritizes_unpositioned_source_generator_diagnostic() -> None:
    tool = RepairBuildFailureTool(_build_registry(_FakeLlm))
    generator_path = "src/Generators/AkkaSerializerGenerator.cs"
    consumer_path = "src/Benchmark/RealBenchmarkMessages.cs"
    output = "\n".join(
        [
            (
                "C:\\Temp\\gate\\src\\Benchmark\\RealBenchmarkMessages.cs(10,2): "
                "error CS0534: does not implement inherited member "
                "[C:\\Temp\\gate\\src\\Benchmark\\Benchmark.csproj]"
            ),
            (
                "CSC : error AKKASG003: Property 'Readings' has unsupported "
                "generated serializer field type [C:\\Temp\\gate\\Benchmark.csproj]"
            ),
        ]
    )

    result = tool.execute(
        problem_summary="Add generated collection support.",
        build_output=output,
        generated_code_by_file={
            generator_path: BROKEN_CSHARP,
            consumer_path: "public class Consumer { }\n",
        },
    )

    assert result["repaired_files"] == [generator_path]
    assert result["diagnostics_by_file"][generator_path][0]["code"] == "AKKASG003"
    assert result["deferred_diagnostics"][0]["code"] == "CS0534"
    assert result["inferred_diagnostic_mappings"] == [
        {
            "diagnostic_file": "CSC",
            "diagnostic_code": "AKKASG003",
            "target_file": generator_path,
        }
    ]


def test_infers_source_generator_from_generated_file_path() -> None:
    diagnostic = SimpleNamespace(
        file=(
            "C:\\Temp\\gate\\src\\Benchmark\\obj\\Debug\\net10.0\\"
            "Akka.Serialization.V2.Generators\\"
            "Akka.Serialization.V2.Generators.AkkaSerializerGenerator\\"
            "RealBenchmarkSerializer.AkkaSerialization.g.cs"
        ),
        code="CS0115",
    )

    target = RepairBuildFailureTool._infer_source_generator_target(
        diagnostic,
        [
            "src/Generators/AkkaSerializerGenerator.cs",
            "src/Benchmark/RealBenchmarkMessages.cs",
        ],
    )

    assert target == "src/Generators/AkkaSerializerGenerator.cs"


def test_repair_prompt_includes_read_only_repository_declarations(tmp_path) -> None:
    """Diagnostics naming a symbol declared elsewhere must carry its signatures.

    Without this the repair loop can keep regenerating the same error because
    the model never sees the contract it has to satisfy.
    """

    base = tmp_path / "src"
    base.mkdir(parents=True)
    (base / "INamedTypeSymbol.cs").write_text(
        "public interface INamedTypeSymbol\n{\n    string Name { get; }\n}\n",
        encoding="utf-8",
    )

    tool = RepairBuildFailureTool(_build_registry(_FakeLlm))

    result = tool.execute(
        problem_summary="Serializer must accept named type symbols.",
        build_output=BUILD_OUTPUT,
        generated_code_by_file={"src/Example.cs": BROKEN_CSHARP},
        repo_path=str(tmp_path),
    )

    file_result = result["file_results"][0]
    assert "src/INamedTypeSymbol.cs" in file_result["related_symbol_files"]

    prompt = file_result["prompt"]
    assert "Related declarations from the repository (read-only)" in prompt
    assert "interface INamedTypeSymbol" in prompt


def test_repair_without_repo_path_reports_no_related_symbols() -> None:
    tool = RepairBuildFailureTool(_build_registry(_FakeLlm))

    result = tool.execute(
        problem_summary="Serializer must accept named type symbols.",
        build_output=BUILD_OUTPUT,
        generated_code_by_file={"src/Example.cs": BROKEN_CSHARP},
    )

    assert result["file_results"][0]["related_symbol_files"] == []


def _large_csharp_source() -> str:
    lines = ["public class LargeExample", "{"]
    lines.extend(
        f'    public string Keep{index:02d} => "keep-{index:02d}";'
        for index in range(1, 19)
    )
    lines[11] = '    public string WrongType => MissingSymbol.Value;'
    lines.append("}")
    return "\n".join(lines) + "\n"


def test_large_file_repairs_only_positioned_chunk_without_truncation() -> None:
    original = _large_csharp_source()
    tool = RepairBuildFailureTool(
        _build_registry(
            _ChunkRepairLlm,
            max_single_shot_code_chars=100,
            chunk_lines=10,
            max_build_repair_chunks=1,
        )
    )
    build_output = (
        "src/LargeExample.cs(12,39): error CS0103: The name 'MissingSymbol' "
        "does not exist in the current context [src/App.csproj]"
    )

    result = tool.execute(
        problem_summary="Rename WrongType to RightType without changing other members.",
        build_output=build_output,
        generated_code_by_file={"src/LargeExample.cs": original},
    )

    repaired = result["generated_code_by_file"]["src/LargeExample.cs"]
    file_result = result["file_results"][0]
    assert result["changed"] is True
    assert file_result["chunked_mode"] is True
    assert file_result["chunk_count"] == 3
    assert len(file_result["selected_chunks"]) == 1
    assert file_result["selected_chunks"][0]["index"] == 1
    assert file_result["selected_chunks"][0]["positioned_diagnostic_lines"] == [12]
    assert file_result["selected_chunks"][0]["selection_reason"] == "diagnostic_line"
    assert "RightType" in repaired
    assert "WrongType" not in repaired
    assert repaired.endswith("\n")
    assert len(repaired.splitlines()) == len(original.splitlines())

    original_chunks = RepairBuildFailureTool._merge_repaired_chunks(
        ApplyPlanSweCodeChangeTool._split_code_chunks(original, 10),
        {},
        final_newline=True,
    )
    assert original_chunks.splitlines()[:10] == repaired.splitlines()[:10]
    assert original_chunks.splitlines()[20:] == repaired.splitlines()[20:]


def test_large_file_rejects_destructively_truncated_chunk() -> None:
    original = _large_csharp_source()
    tool = RepairBuildFailureTool(
        _build_registry(
            _DestructiveChunkLlm,
            max_single_shot_code_chars=100,
            chunk_lines=10,
            max_build_repair_chunks=1,
        )
    )

    result = tool.execute(
        problem_summary="Repair the missing symbol.",
        build_output=(
            "src/LargeExample.cs(12,39): error CS0103: The name 'MissingSymbol' "
            "does not exist in the current context [src/App.csproj]"
        ),
        generated_code_by_file={"src/LargeExample.cs": original},
    )

    assert result["changed"] is False
    assert result["generated_code_by_file"]["src/LargeExample.cs"] == original
    chunk_result = result["file_results"][0]["selected_chunks"][0]
    assert "destructively truncated" in chunk_result["rejected_reason"]
    assert "destructively truncated" in result["file_results"][0]["rejected_reason"]


GENERATOR_CODE = """public sealed class AkkaSerializerGenerator
{
    public void Emit(string name) { }
}
"""

MESSAGES_CODE = """public sealed class RealBenchmarkMessage
{
    public IReadOnlyList<Reading> Readings { get; init; }
}
"""

TOOL_DIAGNOSTIC_OUTPUT = (
    "CSC : error AKKASG003: Property 'Readings' on type 'RealBenchmarkMessage' "
    "has unsupported generated serializer field type 'IReadOnlyList<Reading>' "
    "[C:\\Temp\\gate\\src\\RemotePingPong.csproj]"
)


def _tool_diagnostic_files() -> dict[str, str]:
    return {
        "src/generators/AkkaSerializerGenerator.cs": GENERATOR_CODE,
        "src/bench/RealBenchmarkMessages.cs": MESSAGES_CODE,
    }


def test_positionless_diagnostic_targets_only_its_inferred_owner() -> None:
    tool = RepairBuildFailureTool(_build_registry(_EchoLlm))

    result = tool.execute(
        problem_summary="Support the declared collection type.",
        build_output=TOOL_DIAGNOSTIC_OUTPUT,
        generated_code_by_file=_tool_diagnostic_files(),
    )

    assert list(result["diagnostics_by_file"]) == [
        "src/generators/AkkaSerializerGenerator.cs"
    ]
    assert result["escalated_targets"] == []
    assert result["changed"] is False


def test_escalated_routing_adds_the_file_the_message_names() -> None:
    tool = RepairBuildFailureTool(_build_registry(_EchoLlm))

    result = tool.execute(
        problem_summary="Support the declared collection type.",
        build_output=TOOL_DIAGNOSTIC_OUTPUT,
        generated_code_by_file=_tool_diagnostic_files(),
        escalate_routing=True,
    )

    assert result["escalated_targets"] == ["src/bench/RealBenchmarkMessages.cs"]
    assert "src/bench/RealBenchmarkMessages.cs" in result["diagnostics_by_file"]
    assert (
        result["diagnostics_by_file"]["src/bench/RealBenchmarkMessages.cs"][0]["code"]
        == "AKKASG003"
    )


def test_escalation_never_re_targets_an_already_routed_file() -> None:
    escalated = RepairBuildFailureTool._escalation_targets(
        diagnostics_by_file={
            "src/bench/RealBenchmarkMessages.cs": [
                {"message": "Property 'Readings' on RealBenchmarkMessage"}
            ]
        },
        extra_diagnostics=[],
        code_by_file=_tool_diagnostic_files(),
        max_targets=2,
    )

    assert "src/bench/RealBenchmarkMessages.cs" not in escalated


def test_escalation_is_bounded_by_the_configured_target_limit() -> None:
    escalated = RepairBuildFailureTool._escalation_targets(
        diagnostics_by_file={},
        extra_diagnostics=[
            {"message": "Readings on RealBenchmarkMessage via AkkaSerializerGenerator"}
        ],
        code_by_file=_tool_diagnostic_files(),
        max_targets=1,
    )

    assert len(escalated) == 1

