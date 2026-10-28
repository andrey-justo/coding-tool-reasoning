from __future__ import annotations

from pathlib import Path
import json

import pytest

from src.service.symbol_context_service import (
    RepositorySymbolContextService,
    extract_diagnostic_symbols,
)


def _write(repo: Path, rel_path: str, content: str) -> None:
    target = repo / rel_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


class _Llm:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.prompts = []

    def chat(self, prompt):
        self.prompts.append(prompt)
        response = next(self.responses)
        if callable(response):
            response = response(json.loads(prompt.split("\nInput data:", 1)[1]))
        return json.dumps(response)


def _choose_file(path):
    return lambda payload: {
        "candidate_ids": [
            item["candidate_id"]
            for item in payload["candidates"]
            if item["file"] == path and "class" in item["declarations"][0]["node_type"]
        ],
        "rationale": "The scripted model selected the actual contract.",
    }


def test_extract_diagnostic_symbols_prefers_qualifier_and_drops_keywords():
    messages = [
        '"Child" does not implement inherited abstract member '
        '"BaseSerializer.Serialize(object, string)"'
    ]

    symbols = extract_diagnostic_symbols(messages)

    assert symbols.index("BaseSerializer") < symbols.index("Serialize")
    assert "Child" in symbols
    # Language keywords and primitive types carry no locating power.
    assert "object" not in symbols
    assert "string" not in symbols


def test_extract_diagnostic_symbols_handles_localized_messages():
    messages = [
        '"RealBenchmarkSerializer" não implementa membro abstrato herdado '
        '"SerializerV2.Manifest(object)"'
    ]

    symbols = extract_diagnostic_symbols(messages)

    assert "SerializerV2" in symbols
    assert "RealBenchmarkSerializer" in symbols


def test_extract_diagnostic_symbols_finds_type_inside_nested_loader_exception_quotes():
    symbols = extract_diagnostic_symbols(
        [
            "Generator 'ExampleGenerator' failed to initialize. Exception was of type "
            "'TypeLoadException' with message 'Could not load type 'RecursiveNode' "
            "from assembly 'Producer' because of an invalid self-referential generic field.'."
        ]
    )
    assert symbols[0] == "RecursiveNode"
    assert "ExampleGenerator" in symbols


def test_resolve_returns_declaring_file_signatures(tmp_path: Path):
    _write(
        tmp_path,
        "src/BaseSerializer.cs",
        "namespace Demo;\n"
        "public abstract class BaseSerializer\n"
        "{\n"
        "    public abstract string Manifest(object obj);\n"
        "    public abstract int Serialize(object obj, string name);\n"
        "}\n",
    )
    _write(
        tmp_path,
        "src/Child.cs",
        "namespace Demo;\npublic sealed class Child : BaseSerializer\n{\n}\n",
    )

    contexts = RepositorySymbolContextService().resolve(
        tmp_path,
        [
            '"Child" does not implement inherited abstract member "BaseSerializer.Manifest(object)"'
        ],
        exclude_files=["src/Child.cs"],
    )

    by_file = {context.file: context for context in contexts}
    assert "src/BaseSerializer.cs" in by_file
    assert "src/Child.cs" not in by_file

    signatures = [
        declaration.signature
        for declaration in by_file["src/BaseSerializer.cs"].declarations
    ]
    assert any("abstract class BaseSerializer" in item for item in signatures)
    assert any("Manifest(object obj)" in item for item in signatures)


def test_candidate_declarations_resolve_qualified_nested_type_not_its_reporter():
    message = "Protocol type 'global::Demo.Messages.Packet' requires an identifier."
    source = (
        "namespace Demo;\n"
        "public class Messages\n{\n"
        "    public class Packet\n    {\n    }\n}\n"
    )
    contexts = RepositorySymbolContextService().resolve_candidate_declarations(
        {
            "Messages.cs": source,
            "Other.cs": source.replace("namespace Demo;", "namespace Other;"),
            "ProtocolGenerator.cs": "// Packet is reported here\npublic class ProtocolGenerator {}",
        },
        [message],
    )[message]
    assert [context.file for context in contexts] == ["Messages.cs"]
    assert contexts[0].symbol == "Demo.Messages.Packet"
    assert contexts[0].declarations[0].name == "Packet"
    assert contexts[0].declarations[0].start_line == 4


def test_candidate_declarations_preserve_ambiguity_and_ignore_usage_or_comments():
    messages = [
        "Type 'Packet' requires an identifier.",
        "Type 'Wrong.Packet' requires an identifier.",
    ]
    contexts = RepositorySymbolContextService().resolve_candidate_declarations(
        {
            "One.cs": "namespace One;\npublic class Packet {}",
            "Two.cs": "namespace Two;\npublic class Packet {}",
            "Usage.cs": "// class Packet {}\npublic class Usage { Packet Value; }",
        },
        messages,
    )
    assert {item.file for item in contexts[messages[0]]} == {"One.cs", "Two.cs"}
    assert contexts[messages[1]] == []


def test_candidate_declaration_resolution_uses_current_javascript_source():
    message = "Function 'process_item' is missing a required decorator."
    result = RepositorySymbolContextService().resolve_candidate_declarations(
        {"app.js": "function process_item() {\n    return 42;\n}\n"}, [message]
    )[message]
    assert [item.file for item in result] == ["app.js"]
    assert result[0].declarations[0].node_type == "function_declaration"


def test_resolve_prefers_declaration_over_mere_usage(tmp_path: Path):
    # A file that only *mentions* the symbol must not outrank its declaration.
    _write(
        tmp_path,
        "src/Setup.cs",
        "namespace Demo;\npublic class Setup\n{\n"
        "    internal Widget Widget { get; }\n}\n",
    )
    _write(
        tmp_path,
        "src/Widget.cs",
        "namespace Demo;\npublic abstract class Widget\n{\n"
        "    public abstract void Render();\n}\n",
    )

    client = _Llm([{"symbols": ["Widget"]}, _choose_file("src/Widget.cs")])
    contexts = RepositorySymbolContextService(llm_client=client).resolve(
        tmp_path, ['cannot convert "Widget" to the expected type']
    )

    assert [context.file for context in contexts] == ["src/Widget.cs"]


def test_model_can_select_test_directory_declaration_over_filename_similarity(tmp_path):
    _write(tmp_path, "src/Widget.cs", "namespace Other;\nclass Widget {}")
    _write(tmp_path, "tests/Contract.cs", "namespace Actual;\nclass Widget {}")
    client = _Llm([{"symbols": ["Widget"]}, _choose_file("tests/Contract.cs")])
    contexts = RepositorySymbolContextService(llm_client=client).resolve(
        tmp_path, ["An unquoted localized contract failure."]
    )
    assert [item.file for item in contexts] == ["tests/Contract.cs"]
    assert len(client.prompts) == 2
    assert "Actual.Widget" in client.prompts[1]
    assert "Other.Widget" in client.prompts[1]


@pytest.mark.parametrize("ids", [[999], [-1], [0, 0], [True]])
def test_model_cannot_invent_duplicate_or_coerce_candidate_ids(tmp_path, ids):
    _write(tmp_path, "Widget.cs", "class Widget {}")
    client = _Llm(
        [
            {"symbols": ["Widget"]},
            {"candidate_ids": ids, "rationale": "Invalid selection."},
            {"candidate_ids": ids, "rationale": "Still invalid after the bounded correction."},
        ]
    )
    with pytest.raises(ValueError):
        RepositorySymbolContextService(llm_client=client).resolve(
            tmp_path, ["Widget failed"]
        )


def test_identical_extraction_requests_share_one_model_call():
    client = _Llm([{"symbols": ["Actual.Contract"]}])
    service = RepositorySymbolContextService(llm_client=client)
    assert service.extract_symbols(["unquoted failure"]) == ["Actual.Contract"]
    assert service.extract_symbols(["unquoted failure"]) == ["Actual.Contract"]
    assert len(client.prompts) == 1


def test_duplicate_extracted_symbols_are_not_silently_deduplicated():
    service = RepositorySymbolContextService(llm_client=_Llm([{"symbols": ["A", "A"]}]))
    with pytest.raises(ValueError, match="duplicate"):
        service.extract_symbols(["Failure"])


def test_batched_ownership_requires_explicit_matches_for_every_message():
    service = RepositorySymbolContextService(
        llm_client=_Llm([{"matches": [], "rationale": "Incomplete."}])
    )
    with pytest.raises(ValueError, match="omitted"):
        service.resolve_candidate_declarations(
            {"Widget.cs": "class Widget {}"}, ["Failure"]
        )


def test_candidate_inventory_is_paged_and_partial_ast_evidence_is_explicit():
    response = {
        "matches": [{"message_index": 0, "candidate_ids": []}],
        "rationale": "No owner established on this page.",
    }
    client = _Llm([response, response])
    service = RepositorySymbolContextService(llm_client=client)
    sources = {
        "many.js": "\n".join(f"function f{i}() {{}}" for i in range(161)),
        "unparsed.unknown": "unavailable declarations",
    }
    assert service.resolve_candidate_declarations(sources, ["Failure"]) == {
        "Failure": []
    }
    payloads = [
        json.loads(prompt.split("\nInput data:", 1)[1]) for prompt in client.prompts
    ]
    assert [len(payload["candidates"]) for payload in payloads] == [160, 1]
    assert payloads[0]["inventory_limits"][0]["file"] == "unparsed.unknown"
    assert payloads[0]["inventory_limits"][0]["error"]


def test_candidate_ast_cache_is_invalidated_by_changed_source():
    decision = {
        "matches": [{"message_index": 0, "candidate_ids": [0]}],
        "rationale": "The only supplied declaration.",
    }
    client = _Llm([decision, decision])
    service = RepositorySymbolContextService(llm_client=client)
    assert (
        service.resolve_candidate_declarations(
            {"file.js": "function before() {}"}, ["Failure"]
        )["Failure"][0].symbol
        == "before"
    )
    assert (
        service.resolve_candidate_declarations(
            {"file.js": "function after() {}"}, ["Failure"]
        )["Failure"][0].symbol
        == "after"
    )


def test_resolve_skips_unknown_symbols(tmp_path: Path):
    _write(tmp_path, "src/Widget.cs", "public class Widget {}\n")

    contexts = RepositorySymbolContextService().resolve(
        tmp_path, ['the name "TotallyAbsentSymbol" does not exist']
    )

    assert contexts == []


def test_resolve_returns_empty_for_missing_repository(tmp_path: Path):
    service = RepositorySymbolContextService()

    assert service.resolve(tmp_path / "absent", ['"Widget"']) == []


def test_signature_preserves_literal_attributes_and_multiline_header(tmp_path: Path):
    _write(
        tmp_path,
        "src/Tagged.cs",
        "namespace Demo;\n"
        '[Serializable(Name = "tagged")]\n'
        "public sealed class Tagged\n"
        "{\n}\n",
    )

    contexts = RepositorySymbolContextService().resolve(
        tmp_path, ['type "Tagged" is invalid']
    )

    assert contexts
    assert (
        contexts[0].declarations[0].signature
        == '[Serializable(Name = "tagged")]\npublic sealed class Tagged'
    )


def test_sources_are_read_once_per_repository(tmp_path: Path):
    _write(tmp_path, "src/Widget.cs", "public class Widget {}\n")
    service = RepositorySymbolContextService()

    service.resolve(tmp_path, ['"Widget"'])
    # Deleting the file must not change the second result: the corpus is cached
    # so repair rounds do not re-read the repository on every attempt.
    (tmp_path / "src" / "Widget.cs").unlink()

    assert service._sources_for(tmp_path)
