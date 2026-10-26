from __future__ import annotations

from pathlib import Path

from src.service.symbol_context_service import (
    RepositorySymbolContextService,
    extract_diagnostic_symbols,
)


def _write(repo: Path, rel_path: str, content: str) -> None:
    target = repo / rel_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


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
        ['"Child" does not implement inherited abstract member "BaseSerializer.Manifest(object)"'],
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

    contexts = RepositorySymbolContextService().resolve(
        tmp_path, ['cannot convert "Widget" to the expected type']
    )

    assert [context.file for context in contexts] == ["src/Widget.cs"]


def test_resolve_skips_unknown_symbols(tmp_path: Path):
    _write(tmp_path, "src/Widget.cs", "public class Widget {}\n")

    contexts = RepositorySymbolContextService().resolve(
        tmp_path, ['the name "TotallyAbsentSymbol" does not exist']
    )

    assert contexts == []


def test_resolve_returns_empty_for_missing_repository(tmp_path: Path):
    service = RepositorySymbolContextService()

    assert service.resolve(tmp_path / "absent", ['"Widget"']) == []


def test_signature_skips_attributes_and_decorators(tmp_path: Path):
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
    assert contexts[0].declarations[0].signature.startswith("public sealed class Tagged")


def test_sources_are_read_once_per_repository(tmp_path: Path):
    _write(tmp_path, "src/Widget.cs", "public class Widget {}\n")
    service = RepositorySymbolContextService()

    service.resolve(tmp_path, ['"Widget"'])
    # Deleting the file must not change the second result: the corpus is cached
    # so repair rounds do not re-read the repository on every attempt.
    (tmp_path / "src" / "Widget.cs").unlink()

    assert service._sources_for(tmp_path)
