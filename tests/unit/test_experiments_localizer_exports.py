from __future__ import annotations

import src.experiments.localizer as localizer_module


def test_localizer_module_exports_expected_symbols() -> None:
    expected = {
        "LocalizationHit",
        "LocalizationStrategy",
        "AstMatchingStrategy",
        "FilenameMatchingStrategy",
        "RegexContentMatchingStrategy",
        "SemanticNlpMatchingStrategy",
        "SymbolImpactStrategy",
        "LocalizerResult",
        "RepositoryIssueLocalizer",
        "discover_repository_code_files",
    }

    assert expected.issubset(set(localizer_module.__all__))
    assert callable(localizer_module.discover_repository_code_files)
