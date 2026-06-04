import csv
import json
import logging
import os
from typing import Dict, Iterator, List, Optional, TextIO

from src.models.swe_edge import SweEdge
from src.models.swe_node import SweNode

logger = logging.getLogger(__name__)

_STATIC_NFR_NODES = {
    "nfr_maintainability": (
        "NFR",
        "Maintainability",
        "Maintainability",
        "How easily the system can be changed or extended over time.",
    ),
    "nfr_readability": (
        "NFR",
        "Readability",
        "Readability",
        "How easily developers can understand the code intent and structure.",
    ),
    "nfr_testability": (
        "NFR",
        "Testability",
        "Testability",
        "How easily the system can be verified through automated and manual tests.",
    ),
    "nfr_reliability": (
        "NFR",
        "Reliability",
        "Reliability",
        "How consistently the system performs its required functions without failure.",
    ),
    "nfr_performance": (
        "NFR",
        "Performance",
        "Performance",
        "How efficiently the system uses resources such as CPU memory and network.",
    ),
    "nfr_security": (
        "NFR",
        "Security",
        "Security",
        "How well the system protects data and behavior from unauthorized access or misuse.",
    ),
    "nfr_scalability": (
        "NFR",
        "Scalability",
        "Scalability",
        "How well the system handles increasing load by adding resources.",
    ),
    "nfr_usability": (
        "NFR",
        "Usability",
        "Usability",
        "How easy it is for users to learn and effectively use the system.",
    ),
}

_STATIC_CONCEPT_NODES = {
    "principle_meaningful_names": ("Principle", "Meaningful Names", "Readability"),
    "principle_low_coupling": ("Principle", "Low Coupling", "Maintainability"),
    "principle_encapsulation": ("Principle", "Encapsulation", "Maintainability"),
    "principle_defensive_programming": (
        "Principle",
        "Defensive Programming",
        "Reliability",
    ),
    "principle_fail_fast": ("Principle", "Fail Fast", "Reliability"),
    "principle_immutability": ("Principle", "Immutability", "Reliability"),
    "principle_logging_monitoring": (
        "Principle",
        "Logging and Monitoring",
        "Reliability",
    ),
    "principle_input_validation": (
        "Principle",
        "Input Validation",
        "Security",
    ),
    "principle_separation_of_concerns": (
        "Principle",
        "Separation of Concerns",
        "Maintainability",
    ),
    "principle_interface_segregation": (
        "Principle",
        "Interface Segregation Principle",
        "Maintainability",
    ),
    "principle_clear_error_handling": (
        "Principle",
        "Clear Error Handling",
        "Reliability",
    ),
    "practice_code_reviews": ("Practice", "Code Reviews", "Maintainability"),
    "practice_static_analysis": ("Practice", "Static Analysis", "Maintainability"),
    "practice_continuous_integration": (
        "Practice",
        "Continuous Integration",
        "Reliability",
    ),
    "practice_test_automation": ("Practice", "Test Automation", "Testability"),
    "practice_refactoring": ("Practice", "Refactoring", "Maintainability"),
    "practice_coding_standards": ("Practice", "Coding Standards", "Readability"),
    "practice_pair_programming": ("Practice", "Pair Programming", "Maintainability"),
    "practice_observability": ("Practice", "Observability", "Reliability"),
    "practice_continuous_delivery": (
        "Practice",
        "Continuous Delivery",
        "Reliability",
    ),
    "legacy_system": ("Context", "Legacy System", "Maintainability"),
    "legacy_hotspot": ("Context", "Legacy Hotspot", "Maintainability"),
    "tech_debt_cluster": ("Smell", "Technical Debt Cluster", "Maintainability"),
    "regression_risk": ("Risk", "Regression Risk", "Reliability"),
    "legacy_missing_abstraction": (
        "Smell",
        "Missing Abstraction",
        "Maintainability",
    ),
    "legacy_god_service": ("Smell", "God Service", "Maintainability"),
    "legacy_concrete_dependency": (
        "Smell",
        "Concrete Dependency",
        "Maintainability",
    ),
    "legacy_change_cascade": ("Smell", "Change Cascade", "Maintainability"),
    "legacy_anemic_domain": ("Smell", "Anemic Domain Model", "Maintainability"),
    "sec_input_validation": ("Principle", "Input Validation", "Security"),
    "sec_least_privilege": ("Principle", "Least Privilege", "Security"),
    "sec_authentication": ("Principle", "Authentication", "Security"),
    "sec_authorization": ("Principle", "Authorization", "Security"),
    "sec_audit_logging": ("Principle", "Security Audit Logging", "Security"),
    "sec_secrets_management": ("Practice", "Secrets Management", "Security"),
    "sec_secure_defaults": ("Practice", "Secure Defaults", "Security"),
    "sec_injection": ("Smell", "Injection Risk", "Security"),
    "sec_insecure_deserialization": (
        "Smell",
        "Insecure Deserialization",
        "Security",
    ),
}

_CLEAN_CODE_NODE_ALIASES = {
    "single_responsibility_principle": "principle_single_responsibility",
    "small_functions": "principle_small_functions",
    "dont_repeat_yourself": "principle_dry",
    "class_cohesion": "principle_high_cohesion",
    "open_closed_principle": "principle_open_closed",
    "dependency_inversion_principle": "principle_dependency_injection",
}

_CATEGORY_NFRS = {
    "naming": "Readability",
    "functions": "Readability",
    "comments": "Maintainability",
    "error_handling": "Reliability",
    "classes": "Maintainability",
    "concurrency": "Reliability",
    "unit_tests": "Testability",
    "formatting": "Readability",
    "systems": "Maintainability",
    "general": "Maintainability",
}

_FOLDER_NODE_METADATA = {
    "clean_code": ("folder_clean_code", "Folder", "knowledge/data/clean_code", "Maintainability"),
    "code_smells": ("folder_code_smells", "Folder", "knowledge/data/code_smells", "Maintainability"),
    "refactoring": ("folder_refactoring", "Folder", "knowledge/data/refactoring", "Maintainability"),
    "behavioral": ("folder_behavioral", "Folder", "knowledge/data/behavioral", "Maintainability"),
    "creational": ("folder_creational", "Folder", "knowledge/data/creational", "Maintainability"),
    "structural": ("folder_structural", "Folder", "knowledge/data/structural", "Maintainability"),
    "reliability": ("folder_reliability", "Folder", "knowledge/data/reliability", "Reliability"),
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
    ) -> None:
        # Allow directory paths to be provided explicitly, or read from
        # environment variables as a fallback.
        self._ground_data_dir = ground_data_dir or os.environ.get("SWE_GROUND_DATA_DIR")
        self._linked_data_dir = linked_data_dir or os.environ.get("SWE_LINKED_DATA_DIR")
        self.nodes: Dict[str, SweNode] = {}
        self.edges: List[SweEdge] = []

    @property
    def ground_data_dir(self) -> Optional[str]:
        return self._ground_data_dir

    @property
    def linked_data_dir(self) -> Optional[str]:
        return self._linked_data_dir

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

        self._load_nodes()
        self._load_edges()
        self._ensure_nodes_for_edges()
        logger.info(
            f"Loaded {len(self.nodes)} nodes and {len(self.edges)} edges "
            f"from {self.ground_data_dir} and {self.linked_data_dir}"
        )

    def _load_nodes(self) -> None:
        if not os.path.isdir(self.ground_data_dir):
            logger.warning(f"ground_data_dir does not exist: {self.ground_data_dir}")
            return
        self.nodes.update(self._build_static_nodes())
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
            payload = self._load_json_payload(os.path.join(current_root, "data.json"))
            if not payload:
                continue

            self._register_folder_node(domain)
            if domain == "clean_code":
                self._register_category_node(str(payload.get("category") or ""))

            node = self._build_node_from_payload(domain=domain, slug=slug, payload=payload)
            if node is not None:
                self.nodes[node.id] = node

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
        payload: Dict[str, object],
    ) -> Optional[SweNode]:
        name = str(payload.get("name") or self._humanize(slug))
        description = str(payload.get("problem") or payload.get("source") or "")

        if domain == "clean_code":
            node_id = _CLEAN_CODE_NODE_ALIASES.get(slug, f"clean_code_{slug}")
            node_type = "Principle"
            nfr_category = _CATEGORY_NFRS.get(str(payload.get("category") or ""), "Maintainability")
        elif domain == "code_smells":
            node_id = f"smell_{slug}"
            node_type = "Smell"
            nfr_category = "Maintainability"
        elif domain == "refactoring":
            node_id = f"refactoring_{slug}"
            node_type = "Refactoring"
            nfr_category = "Maintainability"
        elif domain in {"reliability", "behavioral", "creational", "structural"}:
            node_id = f"pattern_{slug}"
            node_type = "Pattern"
            nfr_category = self._infer_pattern_nfr_category(domain=domain, payload=payload)
        else:
            return None

        return SweNode(
            id=node_id,
            type=node_type,
            name=name,
            nfr_category=nfr_category,
            description=description,
        )

    @staticmethod
    def _infer_pattern_nfr_category(domain: str, payload: Dict[str, object]) -> str:
        if domain == "reliability":
            problem = str(payload.get("problem") or "").lower()
            if "security" in problem or "abuse" in problem:
                return "Security"
            if "scale" in problem or "shard" in problem or "partition" in problem:
                return "Scalability"
            if "performance" in problem or "throughput" in problem:
                return "Performance"
            return "Reliability"
        return "Maintainability"

    def _register_folder_node(self, domain: str) -> None:
        metadata = _FOLDER_NODE_METADATA.get(domain)
        if not metadata:
            return
        node_id, node_type, name, nfr_category = metadata
        self.nodes.setdefault(
            node_id,
            SweNode(
                id=node_id,
                type=node_type,
                name=name,
                nfr_category=nfr_category,
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
                nfr_category=_CATEGORY_NFRS.get(category, "Maintainability"),
                description=f"Clean-code guidance grouped under the {category} category.",
            ),
        )

    @staticmethod
    def _build_static_nodes() -> Dict[str, SweNode]:
        nodes: Dict[str, SweNode] = {}
        for node_id, (node_type, name, nfr_category, description) in _STATIC_NFR_NODES.items():
            nodes[node_id] = SweNode(
                id=node_id,
                type=node_type,
                name=name,
                nfr_category=nfr_category,
                description=description,
            )
        for node_id, (node_type, name, nfr_category) in _STATIC_CONCEPT_NODES.items():
            nodes[node_id] = SweNode(
                id=node_id,
                type=node_type,
                name=name,
                nfr_category=nfr_category,
                description="",
            )
        return nodes

    def _ensure_nodes_for_edges(self) -> None:
        for edge in self.edges:
            for node_id in (edge.source_id, edge.target_id):
                if node_id not in self.nodes:
                    self.nodes[node_id] = self._build_fallback_node(node_id)

    def _build_fallback_node(self, node_id: str) -> SweNode:
        node_type = "Concept"
        nfr_category = "Maintainability"
        if node_id.startswith("category_"):
            node_type = "Category"
            nfr_category = _CATEGORY_NFRS.get(node_id.replace("category_", ""), "Maintainability")
        elif node_id.startswith("folder_"):
            node_type = "Folder"
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
            name=self._humanize(node_id),
            nfr_category=nfr_category,
            description="",
        )

    @staticmethod
    def _humanize(value: str) -> str:
        return " ".join(part.capitalize() for part in value.replace("-", "_").split("_") if part)

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
                    if not source or not target:
                        continue
                    self.edges.append(
                        SweEdge(
                            source_id=source,
                            relation=self._clean_cell(row.get("Relation")),
                            target_id=target,
                            description=self._clean_cell(row.get("Description")),
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
