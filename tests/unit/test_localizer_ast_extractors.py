from __future__ import annotations

from pathlib import Path

import pytest

from src.service.localizer.ast.generic_symbol_extractor import GenericSymbolExtractor
from src.service.localizer.ast.python_symbol_extractor import PythonSymbolExtractor
from src.service.localizer.ast.regex_symbol_extractor import RegexSymbolExtractor


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
