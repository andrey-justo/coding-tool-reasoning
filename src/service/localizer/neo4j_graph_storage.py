from __future__ import annotations

import hashlib
import importlib
from pathlib import Path


class Neo4jGraphStorage:
    """Optional Neo4j storage backend for localizer file-relationship graphs."""

    def __init__(
        self,
        *,
        uri: str,
        username: str,
        password: str,
        database: str = "neo4j",
    ) -> None:
        self.database = database
        self._driver = None
        self._available = False

        try:
            neo4j_module = importlib.import_module("neo4j")
            GraphDatabase = getattr(neo4j_module, "GraphDatabase")
            self._driver = GraphDatabase.driver(uri, auth=(username, password))
            self._available = True
        except Exception:
            self._available = False

    @property
    def available(self) -> bool:
        return self._available and self._driver is not None

    @staticmethod
    def _repo_key(repo_path: Path) -> str:
        return hashlib.sha1(str(repo_path.resolve()).encode("utf-8")).hexdigest()[:16]

    def replace_graph(
        self,
        *,
        repo_path: Path,
        definitions_by_file: dict[str, set[str]],
        references_by_file: dict[str, set[str]],
        imports_by_file: dict[str, set[str]],
        neighbors: dict[str, set[str]],
    ) -> None:
        if not self.available:
            return

        repo = self._repo_key(repo_path)
        with self._driver.session(database=self.database) as session:
            session.run("MATCH (n {repo: $repo}) DETACH DELETE n", repo=repo)

            for path, definitions in definitions_by_file.items():
                session.run(
                    "MERGE (:File {repo: $repo, path: $path})",
                    repo=repo,
                    path=path,
                )
                for symbol in definitions:
                    session.run(
                        """
                        MERGE (f:File {repo: $repo, path: $path})
                        MERGE (s:Symbol {repo: $repo, name: $symbol})
                        MERGE (f)-[:DEFINES]->(s)
                        """,
                        repo=repo,
                        path=path,
                        symbol=symbol,
                    )

            for path, refs in references_by_file.items():
                for symbol in refs:
                    session.run(
                        """
                        MERGE (f:File {repo: $repo, path: $path})
                        MERGE (s:Symbol {repo: $repo, name: $symbol})
                        MERGE (f)-[:REFERS]->(s)
                        """,
                        repo=repo,
                        path=path,
                        symbol=symbol,
                    )

            for path, imports in imports_by_file.items():
                for symbol in imports:
                    session.run(
                        """
                        MERGE (f:File {repo: $repo, path: $path})
                        MERGE (s:Symbol {repo: $repo, name: $symbol})
                        MERGE (f)-[:IMPORTS]->(s)
                        """,
                        repo=repo,
                        path=path,
                        symbol=symbol,
                    )

            for source, targets in neighbors.items():
                for target in targets:
                    if source == target:
                        continue
                    session.run(
                        """
                        MERGE (a:File {repo: $repo, path: $source})
                        MERGE (b:File {repo: $repo, path: $target})
                        MERGE (a)-[:RELATED]->(b)
                        """,
                        repo=repo,
                        source=source,
                        target=target,
                    )

    def expand_neighbors(
        self,
        *,
        repo_path: Path,
        seed_files: set[str],
        max_hops: int,
    ) -> dict[str, int]:
        if not self.available or not seed_files:
            return {}

        repo = self._repo_key(repo_path)
        seeds = sorted(seed_files)
        with self._driver.session(database=self.database) as session:
            result = session.run(
                """
                UNWIND $seeds AS seed
                MATCH p=(s:File {repo: $repo, path: seed})-[:RELATED*1..$max_hops]->(n:File {repo: $repo})
                WITH n.path AS path, min(length(p)) AS dist
                RETURN path, dist
                """,
                repo=repo,
                seeds=seeds,
                max_hops=max_hops,
            )

            distances: dict[str, int] = {}
            for row in result:
                path = str(row.get("path") or "")
                if not path:
                    continue
                distance = int(row.get("dist") or 0)
                if distance <= 0:
                    continue
                prev = distances.get(path)
                if prev is None or distance < prev:
                    distances[path] = distance

            for seed in seed_files:
                distances.pop(seed, None)
            return distances
