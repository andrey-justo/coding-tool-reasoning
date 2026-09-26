from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from src.service.localizer.neo4j_graph_storage import Neo4jGraphStorage


class _FakeResult:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self._rows = rows

    def __iter__(self):
        return iter(self._rows)


class _FakeSession:
    def __init__(self, rows: list[dict[str, object]] | None = None) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []
        self._rows = rows or []

    def __enter__(self) -> _FakeSession:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def run(self, query: str, **params: object) -> _FakeResult:
        self.calls.append((query, params))
        if "RETURN path, dist" in query:
            return _FakeResult(self._rows)
        return _FakeResult([])


class _FakeDriver:
    def __init__(self, session: _FakeSession) -> None:
        self._session = session

    def session(self, **kwargs: object) -> _FakeSession:
        return self._session


def test_constructor_sets_unavailable_when_neo4j_import_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _raise_import(_: str) -> object:
        raise ImportError("neo4j missing")

    monkeypatch.setattr(
        "src.service.localizer.neo4j_graph_storage.importlib.import_module",
        _raise_import,
    )

    storage = Neo4jGraphStorage(uri="bolt://localhost", username="u", password="p")
    assert storage.available is False


def test_constructor_sets_available_when_driver_is_created(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_session = _FakeSession()
    fake_driver = _FakeDriver(fake_session)

    class _GraphDatabase:
        @staticmethod
        def driver(uri: str, auth: tuple[str, str]) -> _FakeDriver:
            assert uri == "bolt://db"
            assert auth == ("neo", "pw")
            return fake_driver

    monkeypatch.setattr(
        "src.service.localizer.neo4j_graph_storage.importlib.import_module",
        lambda _: SimpleNamespace(GraphDatabase=_GraphDatabase),
    )

    storage = Neo4jGraphStorage(uri="bolt://db", username="neo", password="pw")
    assert storage.available is True


def test_replace_graph_noops_when_storage_unavailable() -> None:
    storage = Neo4jGraphStorage(uri="", username="", password="")
    storage._available = False
    storage._driver = None

    storage.replace_graph(
        repo_path=Path("."),
        definitions_by_file={},
        references_by_file={},
        imports_by_file={},
        neighbors={},
        ast_links_by_file={},
    )


def test_replace_graph_persists_all_relationship_types(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_session = _FakeSession()
    fake_driver = _FakeDriver(fake_session)
    storage = Neo4jGraphStorage(uri="", username="", password="")
    storage._available = True
    storage._driver = fake_driver

    monkeypatch.setattr(
        Neo4jGraphStorage,
        "_repo_key",
        staticmethod(lambda _: "repo123"),
    )

    storage.replace_graph(
        repo_path=Path("."),
        definitions_by_file={"a.py": {"foo"}},
        references_by_file={"a.py": {"bar"}},
        imports_by_file={"a.py": {"typing"}},
        neighbors={"a.py": {"b.py", "a.py"}},
        ast_links_by_file={"a.py": [("foo", "calls", "bar")]},
    )

    all_queries = "\n".join(query for query, _ in fake_session.calls)
    assert "DETACH DELETE" in all_queries
    assert "DEFINES" in all_queries
    assert "REFERS" in all_queries
    assert "IMPORTS" in all_queries
    assert "RELATED" in all_queries
    assert "AST_LINK" in all_queries

    related_calls = [
        params
        for query, params in fake_session.calls
        if "MERGE (a)-[:RELATED]->(b)" in query
    ]
    assert all(params.get("source") != params.get("target") for params in related_calls)


def test_expand_neighbors_returns_min_distance_and_filters_invalid_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = [
        {"path": "a.py", "dist": 2},
        {"path": "a.py", "dist": 1},
        {"path": "seed.py", "dist": 1},
        {"path": "", "dist": 1},
        {"path": "z.py", "dist": 0},
    ]
    fake_session = _FakeSession(rows=rows)
    storage = Neo4jGraphStorage(uri="", username="", password="")
    storage._available = True
    storage._driver = _FakeDriver(fake_session)

    monkeypatch.setattr(
        Neo4jGraphStorage,
        "_repo_key",
        staticmethod(lambda _: "repo123"),
    )

    distances = storage.expand_neighbors(
        repo_path=Path("."),
        seed_files={"seed.py"},
        max_hops=3,
    )

    assert distances == {"a.py": 1}


def test_expand_neighbors_returns_empty_when_unavailable_or_no_seeds() -> None:
    storage = Neo4jGraphStorage(uri="", username="", password="")
    storage._available = False
    storage._driver = None

    assert storage.expand_neighbors(repo_path=Path("."), seed_files={"a.py"}, max_hops=1) == {}
    assert storage.expand_neighbors(repo_path=Path("."), seed_files=set(), max_hops=1) == {}
