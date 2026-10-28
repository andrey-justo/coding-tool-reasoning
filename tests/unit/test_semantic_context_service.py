"""Tests for the language-agnostic semantic context resolver."""

from __future__ import annotations

import pytest

from src.service.localizer.ast.tree_sitter_symbol_extractor import (
    _LANG_MODULE_BY_SUFFIX,
)
from src.service.semantic_context_service import (
    _CALL_NODE_TYPES,
    SemanticContextService,
)
from src.service.symbol_context_service import RepositorySymbolContextService


def _filler(count: int) -> str:
    return "\n".join(f"        // padding line {index}" for index in range(count))


CSHARP_SOURCE = f"""using System;

namespace Demo
{{
    public class Generator
    {{
        private string GetFullyQualifiedTypeName(INamedTypeSymbol symbol)
        {{
            return symbol.Name;
        }}

{_filler(200)}

        public void Emit(ITypeSymbol type)
        {{
            var name = GetFullyQualifiedTypeName(type);
            Console.WriteLine(name);
        }}
    }}
}}
"""


def _csharp_diagnostic() -> dict[str, object]:
    lines = CSHARP_SOURCE.splitlines()
    line = next(
        index + 1
        for index, text in enumerate(lines)
        if "var name = GetFullyQualifiedTypeName(type);" in text
    )
    column = lines[line - 1].index("type)") + 1
    return {
        "line": line,
        "column": column,
        "code": "CS1503",
        "message": (
            "Argument 1: cannot convert from 'ITypeSymbol' to 'INamedTypeSymbol'"
        ),
    }


def test_resolves_callee_declared_far_from_the_failing_line():
    """The root cause: the contract lives in the same file, outside the excerpt."""

    service = SemanticContextService()

    contexts = service.describe("Generator.cs", CSHARP_SOURCE, [_csharp_diagnostic()])

    assert len(contexts) == 1
    context = contexts[0]
    assert context.available is True
    assert context.call_site is not None
    assert context.call_site.callee == "GetFullyQualifiedTypeName"
    assert context.call_site.arguments == ["type"]

    by_symbol = {symbol.symbol: symbol for symbol in context.symbols}
    callee = by_symbol["GetFullyQualifiedTypeName"]
    assert callee.origin == "target_file"
    assert callee.file == "Generator.cs"
    assert callee.declarations
    assert "INamedTypeSymbol symbol" in callee.declarations[0]["signature"]
    assert "defines_contract" not in callee.declarations[0]
    assert callee.declarations[0]["node_type"] == "method_declaration"


def test_symbols_absent_from_file_and_repository_are_marked_external():
    service = SemanticContextService()

    contexts = service.describe("Generator.cs", CSHARP_SOURCE, [_csharp_diagnostic()])

    origins = {symbol.symbol: symbol.origin for symbol in contexts[0].symbols}
    assert origins["ITypeSymbol"] == "not_found_in_retrieved_context"
    assert origins["INamedTypeSymbol"] == "not_found_in_retrieved_context"


def test_repository_model_failure_is_not_reported_as_an_external_contract(tmp_path):
    class Resolver:
        def declarations_for_symbol(self, *args, **kwargs):
            raise RuntimeError("Declaration model unavailable")

    with pytest.raises(RuntimeError, match="Declaration model unavailable"):
        SemanticContextService().describe(
            "Generator.cs",
            CSHARP_SOURCE,
            [_csharp_diagnostic()],
            repo_path=tmp_path,
            symbol_resolver=Resolver(),
        )


def test_symbol_extraction_is_batched_across_diagnostics():
    class Resolver:
        def __init__(self):
            self.messages = []

        def extract_symbols(self, messages):
            self.messages.append(messages)
            return ["ITypeSymbol", "INamedTypeSymbol"]

    resolver = Resolver()
    diagnostics = [_csharp_diagnostic(), {**_csharp_diagnostic(), "code": "OTHER"}]
    SemanticContextService().describe(
        "Generator.cs",
        CSHARP_SOURCE,
        diagnostics,
        symbol_resolver=resolver,
    )
    assert len(resolver.messages) == 1
    assert len(resolver.messages[0]) == 2


def test_overloaded_declarations_are_all_reported():
    source = """class Box
{
    public void Add(int value) { }

    public void Add(string value) { }

    public void Run()
    {
        Add(1.5);
    }
}
"""
    diagnostic = {
        "line": 9,
        "column": 9,
        "code": "CS1503",
        "message": "cannot convert from 'double' to 'int' in 'Add'",
    }

    contexts = SemanticContextService().describe("Box.cs", source, [diagnostic])

    declarations = next(
        symbol.declarations for symbol in contexts[0].symbols if symbol.symbol == "Add"
    )
    signatures = [item["signature"] for item in declarations]
    assert len(signatures) == 2
    assert any("int value" in signature for signature in signatures)
    assert any("string value" in signature for signature in signatures)


def test_resolution_is_driven_by_the_grammar_table_not_by_csharp():
    """Nothing in the resolver is C#-specific: it keys off the shared grammars."""

    assert {".ts", ".go", ".java", ".rs", ".js", ".cpp"} <= set(_LANG_MODULE_BY_SUFFIX)
    # Call nodes from the JavaScript/Python, Java, Rust and C/C++ grammars.
    assert {"call_expression", "call", "method_invocation", "macro_invocation"} <= (
        _CALL_NODE_TYPES
    )


def test_repository_declarations_are_used_when_the_file_does_not_declare_it(tmp_path):
    helper = tmp_path / "Helper.cs"
    helper.write_text(
        "public class Helper\n"
        "{\n"
        "    public string Normalize(int value) { return value.ToString(); }\n"
        "}\n",
        encoding="utf-8",
    )

    source = """public class Runner
{
    public void Run()
    {
        var helper = new Helper();
    }
}
"""
    diagnostic = {
        "line": 5,
        "column": 22,
        "code": "CS0246",
        "message": "The type or namespace name 'Helper' could not be found",
    }

    contexts = SemanticContextService().describe(
        "Runner.cs",
        source,
        [diagnostic],
        repo_path=tmp_path,
        symbol_resolver=RepositorySymbolContextService(),
    )

    callee = next(symbol for symbol in contexts[0].symbols if symbol.symbol == "Helper")
    assert callee.origin == "repository"
    assert callee.file == "Helper.cs"
    assert callee.declarations


def test_excluded_files_do_not_suppress_target_file_resolution(tmp_path):
    """Exclusion protects against duplication, never against the failing file."""

    source = """public class Runner
{
    public static string Normalize(int value) { return value.ToString(); }

    public void Run()
    {
        var text = Normalize("x");
    }
}
"""
    (tmp_path / "Runner.cs").write_text(source, encoding="utf-8")
    diagnostic = {
        "line": 7,
        "column": 29,
        "code": "CS1503",
        "message": "cannot convert from 'string' to 'int' in 'Normalize'",
    }

    contexts = SemanticContextService().describe(
        "Runner.cs",
        source,
        [diagnostic],
        repo_path=tmp_path,
        symbol_resolver=RepositorySymbolContextService(),
        exclude_files=["Runner.cs"],
    )

    callee = next(
        symbol for symbol in contexts[0].symbols if symbol.symbol == "Normalize"
    )
    assert callee.origin == "target_file"
    assert "int value" in callee.declarations[0]["signature"]


def test_repeated_positions_do_not_consume_the_diagnostic_budget():
    diagnostic = _csharp_diagnostic()

    contexts = SemanticContextService().describe(
        "Generator.cs",
        CSHARP_SOURCE,
        [diagnostic, dict(diagnostic), dict(diagnostic)],
        max_diagnostics=2,
    )

    assert len(contexts) == 1


def test_unparseable_language_degrades_without_raising():
    contexts = SemanticContextService().describe(
        "notes.unknownext",
        "some free text\n",
        [{"line": 1, "column": 1, "code": "X", "message": "boom"}],
    )

    assert len(contexts) == 1
    assert contexts[0].available is False
    assert contexts[0].call_site is None
    assert contexts[0].error
