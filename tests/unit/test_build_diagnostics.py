from src.service.build_diagnostics import (
    BuildDiagnosticContext,
    BuildDiagnosticParserResolver,
    match_diagnostic_file,
)

CS1503_OUTPUT = """
  Determining projects to restore...
C:\\Temp\\issue-mcp-gate-1\\src\\Akka\\Serialization\\AkkaSerializerGenerator.cs(292,48): error CS1503: Argument 1: cannot convert from 'Microsoft.CodeAnalysis.ITypeSymbol' to 'Microsoft.CodeAnalysis.INamedTypeSymbol' [C:\\Temp\\issue-mcp-gate-1\\src\\Akka\\Akka.csproj]
C:\\Temp\\issue-mcp-gate-1\\src\\Akka\\Akka.csproj : warning NU1902: Package 'X' has a known vulnerability
    1 Error(s)
"""


def test_dotnet_parser_extracts_positioned_error():
    result = BuildDiagnosticParserResolver().parse(
        CS1503_OUTPUT,
        BuildDiagnosticContext(language="csharp", project_type="dotnet"),
    )

    assert result.parser == "dotnet"
    assert result.available is True
    assert len(result.diagnostics) == 1

    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "CS1503"
    assert diagnostic.line == 292
    assert diagnostic.column == 48
    assert diagnostic.severity == "error"
    assert "INamedTypeSymbol" in diagnostic.message


def test_dotnet_parser_handles_unpositioned_error():
    result = BuildDiagnosticParserResolver().parse(
        "CSC : error CS5001: Program does not contain a static 'Main' method [a.csproj]",
        BuildDiagnosticContext(project_type="dotnet"),
    )

    assert [diagnostic.code for diagnostic in result.diagnostics] == ["CS5001"]
    assert result.diagnostics[0].line is None


def test_python_parser_extracts_traceback_and_linter_style():
    output = (
        "Traceback (most recent call last):\n"
        '  File "src/app.py", line 12, in <module>\n'
        "    main()\n"
        "TypeError: main() missing 1 required positional argument\n"
        "src/other.py:3:1: F401 'os' imported but unused\n"
    )

    result = BuildDiagnosticParserResolver().parse(
        output, BuildDiagnosticContext(language="python")
    )

    assert result.parser == "python"
    files = {diagnostic.file for diagnostic in result.diagnostics}
    assert "src/app.py" in files


def test_resolver_falls_back_to_generic_when_language_parser_finds_nothing():
    result = BuildDiagnosticParserResolver().parse(
        "make: *** [all] error: linker failed with exit code 1",
        BuildDiagnosticContext(language="python"),
    )

    assert result.parser == "generic"
    assert result.available is True


def test_match_diagnostic_file_maps_temporary_worktree_path():
    known = [
        "src/Akka/Serialization/AkkaSerializerGenerator.cs",
        "src/Akka/Serialization/Other.cs",
    ]

    matched = match_diagnostic_file(
        "C:\\Temp\\issue-mcp-gate-1\\src\\Akka\\Serialization\\AkkaSerializerGenerator.cs",
        known,
    )

    assert matched == "src/Akka/Serialization/AkkaSerializerGenerator.cs"


def test_match_diagnostic_file_falls_back_to_file_name():
    matched = match_diagnostic_file(
        "/build/elsewhere/Other.cs", ["src/Akka/Serialization/Other.cs"]
    )

    assert matched == "src/Akka/Serialization/Other.cs"


def test_match_diagnostic_file_returns_none_for_unknown_file():
    assert match_diagnostic_file("/build/Unknown.cs", ["src/Known.cs"]) is None
    assert match_diagnostic_file(None, ["src/Known.cs"]) is None


def test_errors_take_priority_over_warnings_in_bounded_window():
    output = "\n".join(
        [f"a.csproj : warning NU190{index}: vuln [a.csproj]" for index in range(5)]
        + ["a.cs(1,1): error CS0103: The name 'x' does not exist [a.csproj]"]
    )

    result = BuildDiagnosticParserResolver().parse(
        output, BuildDiagnosticContext(project_type="dotnet"), max_diagnostics=2
    )

    assert [diagnostic.code for diagnostic in result.diagnostics] == ["CS0103"]
