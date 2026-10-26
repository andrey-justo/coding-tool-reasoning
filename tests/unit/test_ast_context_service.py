from src.service.ast_context_service import AstContextService

CSHARP_SOURCE = """namespace Akka.Serialization
{
    public class AkkaSerializerGenerator
    {
        private string GetFullyQualifiedTypeName(INamedTypeSymbol symbol)
        {
            return symbol.ToDisplayString();
        }

        public string Render(ITypeSymbol targetTypeSymbol)
        {
            return GetFullyQualifiedTypeName(targetTypeSymbol!);
        }
    }
}
"""


def test_describe_locations_reports_enclosing_scopes_for_csharp():
    service = AstContextService()

    contexts = service.describe_locations(
        "src/Akka/Serialization/AkkaSerializerGenerator.cs",
        CSHARP_SOURCE,
        [13],
    )

    assert len(contexts) == 1
    context = contexts[0]
    assert context.available is True
    assert context.line == 13
    assert "13: " in context.snippet

    scope_names = {scope.name for scope in context.scopes}
    assert "AkkaSerializerGenerator" in scope_names
    assert "Render" in scope_names


def test_describe_locations_degrades_without_parser():
    service = AstContextService()

    contexts = service.describe_locations(
        "notes.unknownext", "line one\nline two\n", [2]
    )

    assert len(contexts) == 1
    assert contexts[0].available is False
    assert contexts[0].error
    assert "2: line two" in contexts[0].snippet


def test_describe_locations_ignores_invalid_lines_and_bounds_locations():
    service = AstContextService()

    assert service.describe_locations("a.cs", CSHARP_SOURCE, [0, -3]) == []

    contexts = service.describe_locations(
        "a.cs", CSHARP_SOURCE, [3, 5, 7, 9], max_locations=2
    )
    assert [context.line for context in contexts] == [3, 5]


def test_describe_outline_lists_declarations_without_file_content():
    service = AstContextService()

    outline = service.describe_outline(
        "src/Akka/Serialization/AkkaSerializerGenerator.cs", CSHARP_SOURCE
    )

    assert outline.available is True
    names = {declaration.name for declaration in outline.declarations}
    assert {"AkkaSerializerGenerator", "Render", "GetFullyQualifiedTypeName"} <= names
    payload = outline.to_dict()
    assert payload["file"].endswith("AkkaSerializerGenerator.cs")
    assert all(
        set(declaration) == {"node_type", "name", "start_line", "end_line"}
        for declaration in payload["declarations"]
    )


def test_describe_outline_bounds_the_number_of_declarations():
    service = AstContextService()

    outline = service.describe_outline("a.cs", CSHARP_SOURCE, max_declarations=1)

    assert len(outline.declarations) == 1


def test_describe_outline_degrades_without_parser():
    service = AstContextService()

    outline = service.describe_outline("notes.unknownext", "line one\n")

    assert outline.available is False
    assert outline.error
    assert outline.declarations == []


def test_to_dict_is_json_friendly():
    service = AstContextService()

    payload = service.describe_locations("a.cs", CSHARP_SOURCE, [13])[0].to_dict()

    assert payload["file"] == "a.cs"
    assert payload["line"] == 13
    assert isinstance(payload["scopes"], list)
    assert all(isinstance(scope, dict) for scope in payload["scopes"])
