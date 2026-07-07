import csv
import json

from src.service.swe_knowledge_base_service import SweKnowledgeBase


def _write_edge_csv(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as file_handle:
        writer = csv.writer(file_handle)
        writer.writerow(["SourceId", "Relation", "TargetId", "Description"])
        writer.writerows(rows)


def _write_data_json(path, payload):
    with open(path, "w", encoding="utf-8") as file_handle:
        json.dump(payload, file_handle)


def test_swe_knowledge_base_discovers_nodes_from_knowledge_data(tmp_path):
    ground_dir = tmp_path / "knowledge" / "data"
    linked_dir = tmp_path / "knowledge" / "linked_data"

    entry_dir = ground_dir / "clean_code" / "add_meaningful_context"
    entry_dir.mkdir(parents=True)
    payload = {
        "name": "Add Meaningful Context",
        "category": "naming",
        "problem": "Names need enough context to be understood in isolation.",
        "source": "Clean Code",
        "steps": ["Prefer names that reveal role.", "Avoid ambiguous abbreviations."],
    }
    _write_data_json(entry_dir / "data.json", payload)

    linked_dir.mkdir(parents=True)
    _write_edge_csv(
        linked_dir / "knowledge_edges.csv",
        [
            [
                "nfr_readability",
                "maps_to_folder",
                "folder_clean_code",
                "Readability guidance is stored under clean code.",
            ],
            [
                "nfr_readability",
                "organized_as",
                "category_naming",
                "Naming guidance supports readability.",
            ],
            [
                "category_naming",
                "contains",
                "principle_meaningful_names",
                "Stale structural edge that should be replaced by ground truth.",
            ],
        ],
    )

    kb = SweKnowledgeBase(
        ground_data_dir=str(ground_dir),
        linked_data_dir=str(linked_dir),
    )
    kb.load()

    folder_node = kb.get_node("folder_clean_code")
    category_node = kb.get_node("category_naming")
    entry_node = kb.get_node("clean_code_add_meaningful_context")

    assert folder_node is not None
    assert folder_node.type == "Folder"
    assert folder_node.name == "knowledge/data/clean_code"
    assert folder_node.nfr_category == "Readability"

    assert category_node is not None
    assert category_node.type == "Category"
    assert category_node.nfr_category == "Readability"

    assert entry_node is not None
    assert entry_node.type == "Principle"
    assert entry_node.metadata["source"] == "Clean Code"
    assert entry_node.metadata["steps"] == payload["steps"]
    assert entry_node.description.startswith(payload["problem"])

    category_neighbors = kb.get_neighbors(["category_naming"])["category_naming"]
    assert [edge.target_id for edge in category_neighbors] == [
        "clean_code_add_meaningful_context"
    ]

    folder_neighbors = kb.get_neighbors(["folder_clean_code"])["folder_clean_code"]
    assert [edge.target_id for edge in folder_neighbors] == ["category_naming"]


def test_swe_knowledge_base_lazy_loads_node_payload_details(tmp_path):
    ground_dir = tmp_path / "knowledge" / "data"
    linked_dir = tmp_path / "knowledge" / "linked_data"

    entry_dir = ground_dir / "reliability" / "rate_limiting"
    entry_dir.mkdir(parents=True)
    payload = {
        "name": "Rate Limiting Design Pattern",
        "problem": "Reject abusive traffic once request thresholds are exceeded.",
        "source": "Pattern Catalog",
        "steps": ["Count requests per bucket.", "Reject requests above the limit."],
    }
    _write_data_json(entry_dir / "data.json", payload)

    linked_dir.mkdir(parents=True)
    _write_edge_csv(
        linked_dir / "knowledge_edges.csv",
        [
            [
                "nfr_security",
                "implemented_by",
                "pattern_rate_limiting",
                "Rate limiting protects endpoints from abusive traffic.",
            ]
        ],
    )

    kb = SweKnowledgeBase(
        ground_data_dir=str(ground_dir),
        linked_data_dir=str(linked_dir),
        lazy_load_nodes=True,
    )
    kb.load()

    discovered_node = kb.nodes["pattern_rate_limiting"]
    assert discovered_node.name == "Rate Limiting"
    assert discovered_node.metadata == {}
    assert discovered_node.source_path.endswith("data.json")

    hydrated_node = kb.get_node("pattern_rate_limiting")

    assert hydrated_node is not None
    assert hydrated_node.name == payload["name"]
    assert hydrated_node.metadata["source"] == payload["source"]
    assert hydrated_node.metadata["steps"] == payload["steps"]

    summary = kb.summarize_for_prompt(["nfr_security"], depth=2)

    assert "Rate Limiting Design Pattern" in summary
    assert (
        "Key steps: Count requests per bucket.; Reject requests above the limit."
        in summary
    )


def test_swe_knowledge_base_filters_stale_semantic_edges_without_ground_truth_nodes(
    tmp_path,
):
    ground_dir = tmp_path / "knowledge" / "data"
    linked_dir = tmp_path / "knowledge" / "linked_data"

    entry_dir = ground_dir / "clean_code" / "add_meaningful_context"
    entry_dir.mkdir(parents=True)
    _write_data_json(
        entry_dir / "data.json",
        {
            "name": "Add Meaningful Context",
            "category": "naming",
            "problem": "Names need context.",
            "source": "Clean Code",
        },
    )

    linked_dir.mkdir(parents=True)
    _write_edge_csv(
        linked_dir / "knowledge_edges.csv",
        [
            [
                "nfr_readability",
                "maps_to_folder",
                "folder_clean_code",
                "Readability guidance is stored under clean code.",
            ],
            [
                "nfr_readability",
                "organized_as",
                "category_naming",
                "Naming guidance supports readability.",
            ],
            [
                "nfr_readability",
                "supported_by",
                "principle_meaningful_names",
                "Stale semantic edge to a non-existent legacy node.",
            ],
        ],
    )

    kb = SweKnowledgeBase(
        ground_data_dir=str(ground_dir),
        linked_data_dir=str(linked_dir),
    )
    kb.load()

    readability_neighbors = kb.get_neighbors(["nfr_readability"])["nfr_readability"]

    assert [edge.target_id for edge in readability_neighbors] == [
        "folder_clean_code",
        "category_naming",
    ]


def test_swe_knowledge_base_rebuilds_multiple_clean_code_entries_per_category(tmp_path):
    ground_dir = tmp_path / "knowledge" / "data"
    linked_dir = tmp_path / "knowledge" / "linked_data"

    first_entry_dir = ground_dir / "clean_code" / "add_meaningful_context"
    first_entry_dir.mkdir(parents=True)
    _write_data_json(
        first_entry_dir / "data.json",
        {
            "name": "Add Meaningful Context",
            "category": "naming",
            "problem": "Names need context.",
            "source": "Clean Code",
        },
    )

    second_entry_dir = ground_dir / "clean_code" / "avoid_disinformation"
    second_entry_dir.mkdir(parents=True)
    _write_data_json(
        second_entry_dir / "data.json",
        {
            "name": "Avoid Disinformation",
            "category": "naming",
            "problem": "Names should not mislead readers.",
            "source": "Clean Code",
        },
    )

    linked_dir.mkdir(parents=True)
    _write_edge_csv(
        linked_dir / "knowledge_edges.csv",
        [
            [
                "nfr_readability",
                "maps_to_folder",
                "folder_clean_code",
                "Readability guidance is stored under clean code.",
            ],
            [
                "nfr_readability",
                "organized_as",
                "category_naming",
                "Naming guidance supports readability.",
            ],
        ],
    )

    kb = SweKnowledgeBase(
        ground_data_dir=str(ground_dir),
        linked_data_dir=str(linked_dir),
    )
    kb.load()

    folder_neighbors = kb.get_neighbors(["folder_clean_code"])["folder_clean_code"]
    category_neighbors = kb.get_neighbors(["category_naming"])["category_naming"]

    assert [edge.target_id for edge in folder_neighbors] == ["category_naming"]
    assert sorted(edge.target_id for edge in category_neighbors) == [
        "clean_code_add_meaningful_context",
        "clean_code_avoid_disinformation",
    ]


def test_swe_knowledge_base_rebuilt_edges_remain_idempotent_across_loads(tmp_path):
    ground_dir = tmp_path / "knowledge" / "data"
    linked_dir = tmp_path / "knowledge" / "linked_data"

    entry_dir = ground_dir / "clean_code" / "add_meaningful_context"
    entry_dir.mkdir(parents=True)
    _write_data_json(
        entry_dir / "data.json",
        {
            "name": "Add Meaningful Context",
            "category": "naming",
            "problem": "Names need context.",
            "source": "Clean Code",
        },
    )

    linked_dir.mkdir(parents=True)
    _write_edge_csv(
        linked_dir / "knowledge_edges.csv",
        [
            [
                "nfr_readability",
                "maps_to_folder",
                "folder_clean_code",
                "Readability guidance is stored under clean code.",
            ],
            [
                "nfr_readability",
                "organized_as",
                "category_naming",
                "Naming guidance supports readability.",
            ],
        ],
    )

    kb = SweKnowledgeBase(
        ground_data_dir=str(ground_dir),
        linked_data_dir=str(linked_dir),
    )
    kb.load()
    first_edge_snapshot = sorted(
        (edge.source_id, edge.relation, edge.target_id) for edge in kb.edges
    )

    kb.load()
    second_edge_snapshot = sorted(
        (edge.source_id, edge.relation, edge.target_id) for edge in kb.edges
    )

    assert second_edge_snapshot == first_edge_snapshot

