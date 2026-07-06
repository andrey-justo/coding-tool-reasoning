import csv
import json
import logging
import os
from typing import Dict, Iterator, List, Optional, TextIO, Tuple

from src.models.swe_edge import SweEdge
from src.models.swe_node import SweNode

logger = logging.getLogger(__name__)

_STRUCTURAL_RELATIONS = {"maps_to_folder", "organized_as", "contains"}

_KNOWLEDGE_DOMAIN_NODE_KINDS = {
    "clean_code": ("Principle", "clean_code_"),
    "code_smells": ("Smell", "smell_"),
    "refactoring": ("Refactoring", "refactoring_"),
    "reliability": ("Pattern", "pattern_"),
    "behavioral": ("Pattern", "pattern_"),
    "creational": ("Pattern", "pattern_"),
    "structural": ("Pattern", "pattern_"),
}


class SweKnowledgeBase:
    """Loads SWE taxonomy nodes and edges from configurable directories.

    Directory paths must be provided explicitly via constructor arguments,
    environment variables, or configuration. This is intentionally generic:
    it will recursively load all CSVs under those roots that match the
    expected column names, so you can colocate taxonomy data under
    knowledge/linked_data without separate node and edge roots.
    """

    def __init__(
        self,
        ground_data_dir: Optional[str] = None,
        linked_data_dir: Optional[str] = None,
        lazy_load_nodes: bool = False,
    ) -> None:
        # Allow directory paths to be provided explicitly, or read from
        # environment variables as a fallback.
        self._ground_data_dir = ground_data_dir or os.environ.get("SWE_GROUND_DATA_DIR")
        self._linked_data_dir = linked_data_dir or os.environ.get("SWE_LINKED_DATA_DIR")
        self._lazy_load_nodes = lazy_load_nodes
        self.nodes: Dict[str, SweNode] = {}
        self.edges: List[SweEdge] = []
        self._node_specs: Dict[str, Tuple[str, str, str]] = {}
        self._hydrated_node_ids: set[str] = set()
        self._knowledge_entries: Dict[str, Dict[str, str]] = {}
        self._folder_nfr_hints: Dict[str, set[str]] = {}
        self._category_nfr_hints: Dict[str, set[str]] = {}
        self._edge_keys: set[Tuple[str, str, str]] = set()

    @property
    def ground_data_dir(self) -> Optional[str]:
        return self._ground_data_dir

    @property
    def linked_data_dir(self) -> Optional[str]:
        return self._linked_data_dir

    @property
    def lazy_load_nodes(self) -> bool:
        return self._lazy_load_nodes

    @staticmethod
    def _iter_csv_lines(file_obj: TextIO) -> Iterator[str]:
        for line in file_obj:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            yield line

    @staticmethod
    def _clean_cell(value: Optional[str]) -> str:
        return (value or "").strip()

    @staticmethod
    def _iter_csv_paths(root_dir: str) -> Iterator[str]:
        for current_root, _, files in os.walk(root_dir):
            for name in sorted(files):
                if name.lower().endswith(".csv"):
                    yield os.path.join(current_root, name)

    def load(self) -> None:
        """Load all known node and edge CSVs into memory.

        Raises:
            ValueError: If taxonomy directories are not configured.
            FileNotFoundError: If configured directories do not exist.
        """
        if not self.ground_data_dir:
            raise ValueError(
                "ground_data_dir not configured. Provide it via constructor, "
                "SWE_GROUND_DATA_DIR environment variable, or configuration file."
            )
        if not self.linked_data_dir:
            raise ValueError(
                "linked_data_dir not configured. Provide it via constructor, "
                "SWE_LINKED_DATA_DIR environment variable, or configuration file."
            )

        if not os.path.isdir(self.ground_data_dir):
            raise FileNotFoundError(
                f"ground_data_dir does not exist: {self.ground_data_dir}"
            )
        if not os.path.isdir(self.linked_data_dir):
            raise FileNotFoundError(
                f"linked_data_dir does not exist: {self.linked_data_dir}"
            )

        # Rebuild in-memory state on each call so repeated loads are idempotent.
        self.nodes.clear()
        self.edges.clear()
        self._node_specs.clear()
        self._hydrated_node_ids.clear()
        self._knowledge_entries.clear()
        self._folder_nfr_hints.clear()
        self._category_nfr_hints.clear()
        self._edge_keys.clear()

        self._load_nodes()
        self._load_edges()
        self._rebuild_edges_from_ground_truth()
        self._ensure_nodes_for_edges()
        self._infer_nfr_categories()
        logger.info(
            f"Loaded {len(self.nodes)} nodes and {len(self.edges)} edges "
            f"from {self.ground_data_dir} and {self.linked_data_dir}"
        )

    def _load_nodes(self) -> None:
        if not os.path.isdir(self.ground_data_dir):
            logger.warning(f"ground_data_dir does not exist: {self.ground_data_dir}")
            return
        self._load_nodes_from_knowledge_data()
        self._load_nodes_from_csv()

    def _load_nodes_from_csv(self) -> None:
        expected_cols = {"Id", "Type", "Name", "NFRCategory", "Description"}
        for path in self._iter_csv_paths(self.ground_data_dir):
            with open(path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(self._iter_csv_lines(f))
                if not expected_cols.issubset(reader.fieldnames or []):
                    continue
                for row in reader:
                    node_id = self._clean_cell(row.get("Id"))
                    if not node_id:
                        continue
                    self.nodes[node_id] = SweNode(
                        id=node_id,
                        type=self._clean_cell(row.get("Type")),
                        name=self._clean_cell(row.get("Name")),
                        nfr_category=self._clean_cell(row.get("NFRCategory")),
                        description=self._clean_cell(row.get("Description")),
                    )

    def _load_nodes_from_knowledge_data(self) -> None:
        for current_root, _, files in os.walk(self.ground_data_dir):
            if "data.json" not in files:
                continue

            relative_dir = os.path.relpath(current_root, self.ground_data_dir)
            parts = relative_dir.split(os.sep)
            if len(parts) != 2:
                continue

            domain, slug = parts
            data_path = os.path.join(current_root, "data.json")
            node_id = self._resolve_node_id(domain=domain, slug=slug)
            if not node_id:
                continue

            payload = self._load_json_payload(data_path)
            if not payload:
                continue

            self._register_folder_node(domain)
            self._node_specs[node_id] = (domain, slug, data_path)
            self._knowledge_entries[node_id] = {
                "domain": domain,
                "slug": slug,
                "source_path": data_path,
                "category": str(payload.get("category") or "").strip(),
            }

            node_payload: Optional[Dict[str, object]] = None
            if not self.lazy_load_nodes:
                node_payload = payload

            node = self._build_node_from_payload(
                domain=domain,
                slug=slug,
                payload=node_payload,
                source_path=data_path,
            )
            if node is not None:
                self.nodes[node.id] = node
                if node_payload:
                    self._hydrated_node_ids.add(node.id)
                    if domain == "clean_code":
                        self._register_category_node(str(payload.get("category") or ""))

    @staticmethod
    def _load_json_payload(path: str) -> Dict[str, object]:
        try:
            with open(path, "r", encoding="utf-8") as file_handle:
                payload = json.load(file_handle) or {}
        except (OSError, json.JSONDecodeError):
            return {}
        return payload if isinstance(payload, dict) else {}

    def _build_node_from_payload(
        self,
        domain: str,
        slug: str,
        payload: Optional[Dict[str, object]],
        source_path: str,
    ) -> Optional[SweNode]:
        node_id = self._resolve_node_id(domain=domain, slug=slug)
        node_type = self._resolve_node_type(domain=domain)
        if not node_id or not node_type:
            return None

        payload = payload or {}
        name = str(payload.get("name") or self._humanize(slug))
        description = self._build_node_description(payload)
        nfr_category = str(payload.get("nfr_category") or "").strip()

        return SweNode(
            id=node_id,
            type=node_type,
            name=name,
            nfr_category=nfr_category,
            description=description,
            metadata=dict(payload),
            source_path=source_path,
        )

    @staticmethod
    def _build_node_description(payload: Dict[str, object]) -> str:
        if not payload:
            return ""
        problem = str(payload.get("problem") or "").strip()
        source = str(payload.get("source") or "").strip()
        if problem and source:
            return f"{problem} Source: {source}"
        return problem or source

    @staticmethod
    def _resolve_node_id(domain: str, slug: str) -> Optional[str]:
        node_kind = _KNOWLEDGE_DOMAIN_NODE_KINDS.get(domain)
        if not node_kind:
            return None

        _, node_prefix = node_kind
        return f"{node_prefix}{slug}"

    @staticmethod
    def _resolve_node_type(domain: str) -> Optional[str]:
        node_kind = _KNOWLEDGE_DOMAIN_NODE_KINDS.get(domain)
        if not node_kind:
            return None
        node_type, _ = node_kind
        return node_type

    def _register_folder_node(self, domain: str) -> None:
        node_id = f"folder_{domain}"
        self.nodes.setdefault(
            node_id,
            SweNode(
                id=node_id,
                type="Folder",
                name=f"knowledge/data/{domain}",
                nfr_category="",
                description=f"Root folder for {domain.replace('_', ' ')} knowledge entries.",
            ),
        )

    def _register_category_node(self, category: str) -> None:
        if not category:
            return
        node_id = f"category_{category}"
        self.nodes.setdefault(
            node_id,
            SweNode(
                id=node_id,
                type="Category",
                name=self._humanize(category),
                nfr_category="",
                description=f"Clean-code guidance grouped under the {category} category.",
            ),
        )

    def _ensure_nodes_for_edges(self) -> None:
        for edge in self.edges:
            for node_id in (edge.source_id, edge.target_id):
                if node_id not in self.nodes:
                    self.nodes[node_id] = self._build_fallback_node(node_id)

    def _build_fallback_node(self, node_id: str) -> SweNode:
        node_type = "Concept"
        nfr_category = ""
        name = self._humanize(node_id)
        description = ""
        if node_id.startswith("category_"):
            node_type = "Category"
            name = self._humanize(node_id.replace("category_", ""))
            description = f"Taxonomy category discovered for {name.lower()} guidance."
        elif node_id.startswith("folder_"):
            node_type = "Folder"
            folder_name = node_id.replace("folder_", "")
            name = f"knowledge/data/{folder_name}"
            description = (
                f"Root folder for {folder_name.replace('_', ' ')} knowledge entries."
            )
        elif node_id.startswith("nfr_"):
            node_type = "NFR"
            name = self._humanize(node_id.replace("nfr_", ""))
            nfr_category = name
            description = f"Non-functional requirement related to {name.lower()}."
        elif node_id.startswith("practice_"):
            node_type = "Practice"
        elif node_id.startswith("principle_"):
            node_type = "Principle"
        elif node_id.startswith("pattern_"):
            node_type = "Pattern"
        elif node_id.startswith("refactoring_"):
            node_type = "Refactoring"
        elif node_id.startswith("smell_"):
            node_type = "Smell"
        return SweNode(
            id=node_id,
            type=node_type,
            name=name,
            nfr_category=nfr_category,
            description=description,
        )

    def _infer_nfr_categories(self) -> None:
        adjacency: Dict[str, List[str]] = {}
        for edge in self.edges:
            adjacency.setdefault(edge.source_id, []).append(edge.target_id)
            adjacency.setdefault(edge.target_id, []).append(edge.source_id)

        known_categories: Dict[str, str] = {}
        for node_id, node in self.nodes.items():
            existing_category = (node.nfr_category or "").strip()
            if existing_category:
                known_categories[node_id] = existing_category
                continue

            if node.type.upper() == "NFR":
                inferred_category = node.name or self._humanize(
                    node_id.replace("nfr_", "")
                )
                node.nfr_category = inferred_category
                known_categories[node_id] = inferred_category

        changed = True
        while changed:
            changed = False
            for node_id, node in self.nodes.items():
                if (node.nfr_category or "").strip():
                    continue
                for neighbor_id in adjacency.get(node_id, []):
                    inferred_category = known_categories.get(neighbor_id, "").strip()
                    if not inferred_category:
                        continue
                    node.nfr_category = inferred_category
                    known_categories[node_id] = inferred_category
                    changed = True
                    break

    def _ensure_node_details_loaded(self, node_id: str) -> None:
        if node_id in self._hydrated_node_ids:
            return

        spec = self._node_specs.get(node_id)
        if not spec:
            return

        domain, slug, source_path = spec
        payload = self._load_json_payload(source_path)
        if not payload:
            return

        hydrated_node = self._build_node_from_payload(
            domain=domain,
            slug=slug,
            payload=payload,
            source_path=source_path,
        )
        if hydrated_node is None:
            return

        existing_node = self.nodes.get(node_id)
        if existing_node and not hydrated_node.nfr_category:
            hydrated_node.nfr_category = existing_node.nfr_category

        self.nodes[node_id] = hydrated_node
        self._hydrated_node_ids.add(node_id)

        if domain == "clean_code":
            self._register_category_node(str(payload.get("category") or ""))

    def get_node(self, node_id: str, load_details: bool = True) -> Optional[SweNode]:
        if load_details:
            self._ensure_node_details_loaded(node_id)
        return self.nodes.get(node_id)

    @staticmethod
    def _format_node_summary(node: SweNode) -> str:
        category = node.nfr_category or "Uncategorized"
        details: List[str] = []
        if node.description:
            details.append(node.description)

        source = str(node.metadata.get("source") or "").strip()
        if source and source not in details:
            details.append(f"Source: {source}")

        steps = node.metadata.get("steps")
        if isinstance(steps, list):
            clean_steps = [str(step).strip() for step in steps if str(step).strip()]
            if clean_steps:
                details.append(f"Key steps: {'; '.join(clean_steps[:2])}")

        label = f"{node.type}: {node.name} ({category})"
        if not details:
            return label
        return f"{label} - {' '.join(details)}"

    @staticmethod
    def _humanize(value: str) -> str:
        return " ".join(
            part.capitalize() for part in value.replace("-", "_").split("_") if part
        )

    def _add_edge(
        self,
        source_id: str,
        relation: str,
        target_id: str,
        description: str,
    ) -> None:
        edge_key = (source_id, relation, target_id)
        if edge_key in self._edge_keys:
            return
        self._edge_keys.add(edge_key)
        self.edges.append(
            SweEdge(
                source_id=source_id,
                relation=relation,
                target_id=target_id,
                description=description,
            )
        )

    def _is_ground_truth_endpoint(self, node_id: str) -> bool:
        if node_id in self.nodes or node_id in self._node_specs:
            return True
        return node_id.startswith(("nfr_", "folder_", "category_"))

    def _rebuild_edges_from_ground_truth(self) -> None:
        for folder_id, nfr_ids in self._folder_nfr_hints.items():
            domain = folder_id.replace("folder_", "", 1)
            for nfr_id in sorted(nfr_ids):
                self._add_edge(
                    nfr_id,
                    "maps_to_folder",
                    folder_id,
                    f"Discovered knowledge/data/{domain} entries contribute to {self._humanize(nfr_id.replace('nfr_', ''))} guidance.",
                )

        for node_id, entry in self._knowledge_entries.items():
            domain = entry["domain"]
            folder_id = f"folder_{domain}"
            category = entry["category"]

            if domain == "clean_code" and category:
                category_id = f"category_{category}"
                self._register_category_node(category)
                self._add_edge(
                    folder_id,
                    "contains",
                    category_id,
                    f"The clean-code folder contains {category.replace('_', ' ')} guidance discovered from knowledge/data.",
                )
                for nfr_id in sorted(self._category_nfr_hints.get(category_id, set())):
                    self._add_edge(
                        nfr_id,
                        "organized_as",
                        category_id,
                        f"{self._humanize(nfr_id.replace('nfr_', ''))} guidance is organized under the {category.replace('_', ' ')} category discovered from knowledge/data.",
                    )
                self._add_edge(
                    category_id,
                    "contains",
                    node_id,
                    f"The {category.replace('_', ' ')} category contains the {entry['slug'].replace('_', ' ')} entry from knowledge/data.",
                )
                continue

            self._add_edge(
                folder_id,
                "contains",
                node_id,
                f"The {domain.replace('_', ' ')} folder contains the {entry['slug'].replace('_', ' ')} entry from knowledge/data.",
            )

    def _load_edges(self) -> None:
        expected_cols = {"SourceId", "Relation", "TargetId", "Description"}
        if not os.path.isdir(self.linked_data_dir):
            return
        for path in self._iter_csv_paths(self.linked_data_dir):
            with open(path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(self._iter_csv_lines(f))
                if not reader.fieldnames or not set(reader.fieldnames).issuperset(
                    expected_cols
                ):
                    continue
                for row in reader:
                    source = self._clean_cell(row.get("SourceId"))
                    target = self._clean_cell(row.get("TargetId"))
                    relation = self._clean_cell(row.get("Relation"))
                    description = self._clean_cell(row.get("Description"))
                    if not source or not target:
                        continue
                    if relation == "maps_to_folder" and target.startswith("folder_"):
                        self._folder_nfr_hints.setdefault(target, set()).add(source)
                    elif relation == "organized_as" and target.startswith("category_"):
                        self._category_nfr_hints.setdefault(target, set()).add(source)

                    if relation in _STRUCTURAL_RELATIONS:
                        continue
                    if not self._is_ground_truth_endpoint(source):
                        continue
                    if not self._is_ground_truth_endpoint(target):
                        continue

                    self._add_edge(source, relation, target, description)

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
            node = self.get_node(node_id)
            if not node:
                return
            label = self._format_node_summary(node)
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
                        target = self.get_node(e.target_id)
                        target_label = target.name if target else e.target_id
                        lines.append(
                            f"{indent}  - {e.relation}: {target_label} - {e.description}"
                        )

        for nid in nfr_ids:
            _expand(nid, 1, "")

        return "\n".join(lines)

    def get_all_nfrs(self) -> List[SweNode]:
        return [n for n in self.nodes.values() if n.type.upper() == "NFR"]
