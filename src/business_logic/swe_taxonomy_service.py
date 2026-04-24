import csv
import os
from typing import Dict, List, Optional

from ..models.swe_edge import SweEdge
from ..models.swe_node import SweNode


class SweKnowledgeBase:
    """Loads SWE taxonomy nodes and edges from taxonomies/ground_data and linked_data.

    This is intentionally generic: it will load all CSVs in those folders that
    match the expected column names, so you can add more taxonomies later.
    """

    def __init__(
        self,
        repo_root: Optional[str] = None,
        ground_data_dir: Optional[str] = None,
        linked_data_dir: Optional[str] = None,
    ) -> None:
        self.repo_root = repo_root or os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..")
        )
        # Optional directory overrides allow new or alternative SWE taxonomies
        # to be plugged in via configuration.
        self._ground_data_dir = ground_data_dir
        self._linked_data_dir = linked_data_dir
        self.nodes: Dict[str, SweNode] = {}
        self.edges: List[SweEdge] = []

    @property
    def ground_data_dir(self) -> str:
        if self._ground_data_dir:
            return self._ground_data_dir
        return os.path.join(self.repo_root, "taxonomies", "ground_data")

    @property
    def linked_data_dir(self) -> str:
        if self._linked_data_dir:
            return self._linked_data_dir
        return os.path.join(self.repo_root, "taxonomies", "linked_data")

    def load(self) -> None:
        """Load all known node and edge CSVs into memory."""

        self._load_nodes()
        self._load_edges()

    def _load_nodes(self) -> None:
        expected_cols = {"Id", "Type", "Name", "NFRCategory", "Description"}
        if not os.path.isdir(self.ground_data_dir):
            return
        for name in os.listdir(self.ground_data_dir):
            if not name.lower().endswith(".csv"):
                continue
            path = os.path.join(self.ground_data_dir, name)
            with open(path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                if not expected_cols.issubset(reader.fieldnames or []):
                    continue
                for row in reader:
                    node_id = row["Id"].strip()
                    if not node_id:
                        continue
                    self.nodes[node_id] = SweNode(
                        id=node_id,
                        type=row.get("Type", "").strip(),
                        name=row.get("Name", "").strip(),
                        nfr_category=row.get("NFRCategory", "").strip(),
                        description=row.get("Description", "").strip(),
                    )

    def _load_edges(self) -> None:
        expected_cols = {"SourceId", "Relation", "TargetId", "Description"}
        if not os.path.isdir(self.linked_data_dir):
            return
        for name in os.listdir(self.linked_data_dir):
            if not name.lower().endswith(".csv"):
                continue
            path = os.path.join(self.linked_data_dir, name)
            with open(path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                if not reader.fieldnames or not set(reader.fieldnames).issuperset(
                    expected_cols
                ):
                    continue
                for row in reader:
                    source = row.get("SourceId", "").strip()
                    target = row.get("TargetId", "").strip()
                    if not source or not target:
                        continue
                    self.edges.append(
                        SweEdge(
                            source_id=source,
                            relation=row.get("Relation", "").strip(),
                            target_id=target,
                            description=row.get("Description", "").strip(),
                        )
                    )

    def find_nfr_ids(self, nfr_names_or_ids: List[str]) -> List[str]:
        """Resolve a list of NFR names or IDs to node IDs."""

        requested = {v.lower() for v in nfr_names_or_ids}
        resolved: List[str] = []
        for node in self.nodes.values():
            if node.type.upper() == "NFR":
                if (
                    node.id.lower() in requested
                    or node.name.lower() in requested
                    or node.nfr_category.lower() in requested
                ):
                    resolved.append(node.id)
        return resolved

    def get_neighbors(self, node_ids: List[str]) -> Dict[str, List[SweEdge]]:
        """Return outgoing edges for the given node IDs."""

        node_set = set(node_ids)
        neighbors: Dict[str, List[SweEdge]] = {nid: [] for nid in node_ids}
        for edge in self.edges:
            if edge.source_id in node_set:
                neighbors.setdefault(edge.source_id, []).append(edge)
        return neighbors

    def summarize_for_prompt(self, nfr_ids: List[str], depth: int = 1) -> str:
        """Build a compact text summary suitable for prompt injection.

        Args:
            nfr_ids: Starting node IDs (typically resolved NFR ids).
            depth: How many relationship hops to traverse (default 1 = direct
                   neighbours only). Honour ``TaxonomyConfig.relationship_depth``
                   by passing ``config.taxonomy.relationship_depth`` here.
        """

        lines: List[str] = []
        visited: set = set()

        def _expand(node_id: str, current_depth: int, indent: str) -> None:
            if node_id in visited or current_depth > depth:
                return
            visited.add(node_id)
            node = self.nodes.get(node_id)
            if not node:
                return
            label = (
                f"{node.type}: {node.name} ({node.nfr_category}) - {node.description}"
            )
            lines.append(f"{indent}{label}")
            if current_depth < depth:
                for e in self.edges:
                    if e.source_id == node_id:
                        rel_line = f"{indent}  [{e.relation}] →"
                        lines.append(rel_line)
                        _expand(e.target_id, current_depth + 1, indent + "    ")
            else:
                for e in self.edges:
                    if e.source_id == node_id:
                        target = self.nodes.get(e.target_id)
                        target_label = target.name if target else e.target_id
                        lines.append(
                            f"{indent}  - {e.relation}: {target_label} - {e.description}"
                        )

        for nid in nfr_ids:
            _expand(nid, 1, "")

        return "\n".join(lines)

    def get_all_nfrs(self) -> List[SweNode]:
        return [n for n in self.nodes.values() if n.type.upper() == "NFR"]
