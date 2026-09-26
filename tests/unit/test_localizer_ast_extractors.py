from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from src.service.localizer.ast.generic_symbol_extractor import GenericSymbolExtractor
from src.service.localizer.ast.python_symbol_extractor import PythonSymbolExtractor
from src.service.localizer.ast.regex_symbol_extractor import RegexSymbolExtractor
from src.service.localizer.ast.tree_sitter_symbol_extractor import (
    TreeSitterSymbolExtractor,
)


def test_generic_symbol_extractor_raises_not_implemented() -> None:
    extractor = GenericSymbolExtractor()
    with pytest.raises(NotImplementedError):
        extractor.extract(Path("x.py"), "print('x')")


def test_python_symbol_extractor_returns_empty_on_syntax_error() -> None:
    extractor = PythonSymbolExtractor()
    symbols = extractor.extract(Path("bad.py"), "def broken(:\n")
    assert symbols.definitions == set()


def test_python_symbol_extractor_extracts_class_and_function_names() -> None:
    extractor = PythonSymbolExtractor()
    source = """
class RetryPolicy:
    pass

async def execute_async():
    return 1

def run():
    return 2
"""
    symbols = extractor.extract(Path("ok.py"), source)
    assert {"retrypolicy", "execute_async", "run"}.issubset(symbols.definitions)


def test_regex_symbol_extractor_extracts_common_non_python_symbols() -> None:
    extractor = RegexSymbolExtractor()
    source = """
public class AuthService {
  public void RetryFlow() { }
}
interface IAuthContract {}
enum AuthState { Ready }
"""
    symbols = extractor.extract(Path("AuthService.java"), source)
    assert "authservice" in symbols.definitions
    assert "retryflow" in symbols.definitions
    assert "iauthcontract" in symbols.definitions
    assert "authstate" in symbols.definitions


def test_tree_sitter_symbol_extractor_gracefully_falls_back_when_unavailable() -> None:
    extractor = TreeSitterSymbolExtractor()
    symbols = extractor.extract(
        Path("AuthService.java"),
        "public class AuthService { public void RetryFlow() {} }",
    )
    # Optional parser modules may not be installed in all environments.
    # Strategy should remain safe and simply return no symbols.
    assert isinstance(symbols.definitions, set)


def test_tree_sitter_symbol_extractor_extracts_symbols_with_fake_parser(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _FakeNode:
        def __init__(self, node_type: str, token: str = "", children=None, name_node=None) -> None:
            self.type = node_type
            self.children = children or []
            self._name_node = name_node
            self.token = token
            self.start_byte = 0
            self.end_byte = 0

        def child_by_field_name(self, field_name: str):
            if field_name == "name":
                return self._name_node
            return None

    class _FakeParser:
        def __init__(self) -> None:
            self._language = None

        def set_language(self, language) -> None:
            self._language = language

        def parse(self, _source_bytes: bytes):
            class_name = _FakeNode("identifier", "AuthService")
            class_decl = _FakeNode(
                "class_declaration",
                children=[_FakeNode("identifier", "AuthService")],
                name_node=class_name,
            )
            method_name = _FakeNode("identifier", "RetryFlow")
            method_decl = _FakeNode(
                "method_declaration",
                children=[_FakeNode("identifier", "RetryFlow")],
                name_node=method_name,
            )
            var_decl = _FakeNode(
                "variable_declarator",
                children=[_FakeNode("identifier", "run")],
            )
            root = _FakeNode("program", children=[class_decl, method_decl, var_decl])
            return SimpleNamespace(root_node=root)

    class _FakeLanguageModule:
        @staticmethod
        def language():
            return _FakeTSModule.Language()

    class _FakeTSModule:
        class Language:
            def __init__(self, *_args, **_kwargs):
                return None

        class Parser:
            def __call__(self, *_args, **_kwargs):
                return _FakeParser()

            def __new__(cls, *_args, **_kwargs):
                return _FakeParser()

    def _fake_import(module_name: str):
        if module_name == "tree_sitter":
            return _FakeTSModule
        if module_name == "tree_sitter_java":
            return _FakeLanguageModule
        raise ImportError(module_name)

    monkeypatch.setattr(
        "src.service.localizer.ast.tree_sitter_symbol_extractor.importlib.import_module",
        _fake_import,
    )
    monkeypatch.setattr(
        TreeSitterSymbolExtractor,
        "_node_text",
        staticmethod(lambda _source_bytes, node: getattr(node, "token", "")),
    )

    extractor = TreeSitterSymbolExtractor()
    symbols = extractor.extract(
        Path("AuthService.java"),
        "public class AuthService { public void RetryFlow() { const run = 1; } }",
    )
    assert {"authservice", "retryflow", "run"}.issubset(symbols.definitions)

    parser1 = extractor._create_parser(".java")
    parser2 = extractor._create_parser(".java")
    assert parser1 is parser2


def test_tree_sitter_symbol_extractor_handles_parse_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _RaisingParser:
        def set_language(self, _language) -> None:
            return None

        def parse(self, _source_bytes: bytes):
            raise RuntimeError("parse failed")

    class _FakeLanguageModule:
        @staticmethod
        def language():
            return object()

    class _FakeTSModule:
        Language = type("Language", (), {})

        class Parser:
            def __call__(self, *_args, **_kwargs):
                return _RaisingParser()

            def __new__(cls, *_args, **_kwargs):
                return _RaisingParser()

    def _fake_import(module_name: str):
        if module_name == "tree_sitter":
            return _FakeTSModule
        if module_name == "tree_sitter_java":
            return _FakeLanguageModule
        raise ImportError(module_name)

    monkeypatch.setattr(
        "src.service.localizer.ast.tree_sitter_symbol_extractor.importlib.import_module",
        _fake_import,
    )

    extractor = TreeSitterSymbolExtractor()
    symbols = extractor.extract(Path("AuthService.java"), "class X {}")
    assert symbols.definitions == set()
