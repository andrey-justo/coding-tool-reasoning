from __future__ import annotations

from pathlib import Path

from src.service.localizer import RepositoryIssueLocalizer
from src.service.localizer.strategies.ast_matching import AstMatchingStrategy
from src.service.localizer.strategies.graph_memory import (
    GraphMemoryRelationshipStrategy,
)
from src.service.localizer.strategies.regex_content import RegexContentMatchingStrategy
from src.service.localizer.strategies.semantic_nlp import SemanticNlpMatchingStrategy
from src.service.localizer.strategies.symbol_impact import SymbolImpactStrategy


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_regex_content_strategy_matches_word_boundaries(tmp_path: Path) -> None:
    _write(
        tmp_path / "src" / "auth_service.py",
        "def process_retry(request):\n    return request\n",
    )

    strategy = RegexContentMatchingStrategy()
    hits = strategy.score(
        repo_path=tmp_path,
        issue_text="retry request fails",
        candidate_paths=["src/auth_service.py"],
    )

    assert "src/auth_service.py" in hits
    assert hits["src/auth_service.py"].score > 0


def test_semantic_nlp_strategy_ranks_related_document_higher(tmp_path: Path) -> None:
    _write(
        tmp_path / "src" / "auth_retry.py",
        "retry logic handles transient network timeout and backoff strategy",
    )
    _write(
        tmp_path / "src" / "ui_theme.py",
        "colors fonts spacing for dashboard header widgets",
    )

    strategy = SemanticNlpMatchingStrategy()
    hits = strategy.score(
        repo_path=tmp_path,
        issue_text="retry timeout backoff behavior",
        candidate_paths=["src/auth_retry.py", "src/ui_theme.py"],
    )

    ui_score = hits["src/ui_theme.py"].score if "src/ui_theme.py" in hits else 0.0
    assert "src/auth_retry.py" in hits
    assert hits["src/auth_retry.py"].score > ui_score


def test_symbol_impact_strategy_finds_dependent_python_file(tmp_path: Path) -> None:
    _write(
        tmp_path / "src" / "core.py",
        "class RetryPolicy:\n    pass\n",
    )
    _write(
        tmp_path / "src" / "service.py",
        "from src.core import RetryPolicy\n\n\ndef run():\n    x = RetryPolicy()\n    return x\n",
    )

    strategy = SymbolImpactStrategy()
    hits = strategy.score(
        repo_path=tmp_path,
        issue_text="Refactor RetryPolicy behavior",
        candidate_paths=["src/core.py", "src/service.py"],
    )

    assert "src/core.py" in hits
    assert "src/service.py" in hits


def test_graph_memory_strategy_propagates_to_related_file(tmp_path: Path) -> None:
    _write(
        tmp_path / "src" / "retry_core.py",
        "class RetryPolicy:\n    pass\n",
    )
    _write(
        tmp_path / "src" / "retry_service.py",
        (
            "from src.retry_core import RetryPolicy\n\n"
            "def run_retry():\n"
            "    policy = RetryPolicy()\n"
            "    return policy\n"
        ),
    )

    strategy = GraphMemoryRelationshipStrategy(hops=2)
    hits = strategy.score(
        repo_path=tmp_path,
        issue_text="Refactor RetryPolicy behavior",
        candidate_paths=["src/retry_core.py", "src/retry_service.py"],
    )

    assert "src/retry_core.py" in hits
    assert "src/retry_service.py" in hits
    assert hits["src/retry_service.py"].score > 0
    assert any(
        "graph hop" in reason or "references issue symbols" in reason
        for reason in hits["src/retry_service.py"].reasons
    )


def test_repository_issue_localizer_combines_strategies(tmp_path: Path) -> None:
    _write(
        tmp_path / "src" / "auth_manager.py",
        "def authenticate_with_retry(token):\n    return token\n",
    )
    _write(
        tmp_path / "src" / "view.py",
        "def render_page():\n    return 'ok'\n",
    )

    localizer = RepositoryIssueLocalizer()
    result = localizer.localize(
        repo_path=tmp_path,
        issue_text="authentication retry failing in manager",
        top_k=1,
        candidate_paths=["src/auth_manager.py", "src/view.py"],
    )

    assert result.selected_files
    assert result.selected_files[0] == "src/auth_manager.py"
    assert any(item["path"] == "src/auth_manager.py" for item in result.details)


def test_generic_ast_strategy_matches_non_python_symbols(tmp_path: Path) -> None:
    _write(
        tmp_path / "src" / "AuthService.java",
        "public class AuthService { public void retryFlow() {} }",
    )

    strategy = AstMatchingStrategy()
    hits = strategy.score(
        repo_path=tmp_path,
        issue_text="Refactor AuthService retryFlow behavior",
        candidate_paths=["src/AuthService.java"],
    )

    assert "src/AuthService.java" in hits
    assert hits["src/AuthService.java"].score > 0


def test_repository_issue_localizer_can_disable_semantic_nlp() -> None:
    localizer = RepositoryIssueLocalizer(enable_semantic_nlp=False)
    assert all(strategy.name != "semantic_nlp" for strategy in localizer.strategies)

    localizer_with_nlp = RepositoryIssueLocalizer(enable_semantic_nlp=True)
    assert any(
        strategy.name == "semantic_nlp" for strategy in localizer_with_nlp.strategies
    )


def test_repository_issue_localizer_can_disable_graph_memory() -> None:
    localizer = RepositoryIssueLocalizer(enable_graph_memory=False)
    assert all(strategy.name != "graph_memory" for strategy in localizer.strategies)

    localizer_with_graph = RepositoryIssueLocalizer(enable_graph_memory=True)
    assert any(strategy.name == "graph_memory" for strategy in localizer_with_graph.strategies)
