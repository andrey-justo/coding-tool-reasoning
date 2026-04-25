import json

import pytest

from src.migration.analyzer import Analyzer
from src.migration.explainer import Explainer
from src.migration.prompt import Prompt
from src.business_logic.swe_taxonomy_service import SweKnowledgeBase
from src.models import swe_models
from src.models.code_gen_plan import CodeGenPlan
from src.models.swe_config import SweMcpConfig
from src.models.swe_context import SweContext
from src.models.swe_explanation import SweCodeChangeExplanation
from src.models.swe_server_context import SweServerContext
from src.tools import judge_code_changes_step as judge_module
from src.tools.judge_code_changes_step import JudgeCodeChangesStep
from src.utils.file_reader import read_file


def test_analyzer_returns_expected_keys():
    analyzer = Analyzer(code="class A {}", prompt="migrate")
    result = analyzer.analyze()

    assert set(result.keys()) == {"why", "how", "unsafe"}
    assert "migration" in result["why"].lower()


def test_explainer_with_missing_fields_uses_defaults():
    explainer = Explainer({"why": "Because"})
    why, how, unsafe = explainer.explain()

    assert why == "Because"
    assert how == ""
    assert unsafe == ""


def test_prompt_get_details_returns_original_text():
    prompt = Prompt("Refactor this code")
    assert prompt.get_details() == "Refactor this code"


def test_swe_knowledge_base_requires_explicit_paths():
    # Without paths, SweKnowledgeBase should fail on load()
    kb = SweKnowledgeBase()

    with pytest.raises(ValueError, match="not configured"):
        kb.load()


def test_swe_knowledge_base_validates_directory_existence():
    # With non-existent paths, SweKnowledgeBase should fail
    kb = SweKnowledgeBase(
        ground_data_dir="/nonexistent/ground",
        linked_data_dir="/nonexistent/linked",
    )

    with pytest.raises(FileNotFoundError):
        kb.load()


def test_swe_knowledge_base_loads_nodes_edges_and_summarizes(tmp_path):
    ground_dir = tmp_path / "taxonomies" / "ground_data"
    linked_dir = tmp_path / "taxonomies" / "linked_data"
    ground_dir.mkdir(parents=True)
    linked_dir.mkdir(parents=True)

    (ground_dir / "nodes.csv").write_text(
        "Id,Type,Name,NFRCategory,Description\n"
        "NFR-1,NFR,Reliability,Reliability,Improves uptime\n"
        "PRA-1,Practice,Retry Logic,Reliability,Retries transient failures\n"
        "SMELL-1,Smell,Long Method,Maintainability,Hard to read\n",
        encoding="utf-8",
    )
    (linked_dir / "edges.csv").write_text(
        "SourceId,Relation,TargetId,Description\n"
        "NFR-1,related_to,PRA-1,Supports reliability\n"
        "NFR-1,avoids,SMELL-1,Prevents complex logic\n",
        encoding="utf-8",
    )

    kb = SweKnowledgeBase(
        ground_data_dir=str(ground_dir),
        linked_data_dir=str(linked_dir),
    )
    kb.load()

    assert kb.find_nfr_ids(["Reliability"]) == ["NFR-1"]
    assert kb.get_neighbors(["NFR-1"])["NFR-1"][0].target_id == "PRA-1"
    assert [node.id for node in kb.get_all_nfrs()] == ["NFR-1"]

    summary = kb.summarize_for_prompt(["NFR-1"], depth=1)
    assert "NFR: Reliability" in summary
    assert "related_to: Retry Logic" in summary


def test_swe_knowledge_base_load_is_idempotent(tmp_path):
    ground_dir = tmp_path / "taxonomies" / "ground_data"
    linked_dir = tmp_path / "taxonomies" / "linked_data"
    ground_dir.mkdir(parents=True)
    linked_dir.mkdir(parents=True)

    (ground_dir / "nodes.csv").write_text(
        "Id,Type,Name,NFRCategory,Description\n"
        "NFR-1,NFR,Reliability,Reliability,Improves uptime\n",
        encoding="utf-8",
    )
    (linked_dir / "edges.csv").write_text(
        "SourceId,Relation,TargetId,Description\n"
        "NFR-1,related_to,NFR-1,Self relation\n",
        encoding="utf-8",
    )

    kb = SweKnowledgeBase(
        ground_data_dir=str(ground_dir),
        linked_data_dir=str(linked_dir),
    )

    kb.load()
    first_nodes_count = len(kb.nodes)
    first_edges_count = len(kb.edges)

    kb.load()

    assert len(kb.nodes) == first_nodes_count
    assert len(kb.edges) == first_edges_count


def test_swe_knowledge_base_ignores_blank_and_comment_lines(tmp_path):
    ground_dir = tmp_path / "taxonomies" / "ground_data"
    linked_dir = tmp_path / "taxonomies" / "linked_data"
    ground_dir.mkdir(parents=True)
    linked_dir.mkdir(parents=True)

    (ground_dir / "nodes.csv").write_text(
        "# taxonomy nodes\n"
        "\n"
        "Id,Type,Name,NFRCategory,Description\n"
        "\n"
        "# section break\n"
        "NFR-1,NFR,Reliability,Reliability,Improves uptime\n",
        encoding="utf-8",
    )
    (linked_dir / "edges.csv").write_text(
        "# taxonomy edges\n"
        "SourceId,Relation,TargetId,Description\n"
        "\n"
        "# section break\n"
        "NFR-1,related_to,NFR-1,Supports reliability\n",
        encoding="utf-8",
    )

    kb = SweKnowledgeBase(
        ground_data_dir=str(ground_dir),
        linked_data_dir=str(linked_dir),
    )

    kb.load()

    assert list(kb.nodes) == ["NFR-1"]
    assert len(kb.edges) == 1
    assert kb.edges[0].relation == "related_to"


def test_swe_config_load_reads_yaml_and_falls_back_for_invalid_files(tmp_path):
    default_config = SweMcpConfig.load(str(tmp_path))
    assert default_config.taxonomy.relationship_depth == 1

    config_path = tmp_path / "swe_mcp_config.yaml"
    config_path.write_text(
        json.dumps(
            {
                "taxonomy": {"relationship_depth": 2},
                "planning": {"max_steps": 3},
                "judging": {"max_risks": 2},
            }
        ),
        encoding="utf-8",
    )

    loaded_config = SweMcpConfig.load(str(tmp_path))
    assert loaded_config.taxonomy.relationship_depth == 2
    assert loaded_config.planning.max_steps == 3
    assert loaded_config.judging.max_risks == 2

    config_path.write_text("not: [valid", encoding="utf-8")

    fallback_config = SweMcpConfig.load(str(tmp_path))
    assert fallback_config.taxonomy.relationship_depth == 1


def test_swe_models_reexports_and_server_context_fields():
    plan = swe_models.CodeGenPlan(problem_description="Refactor controller")
    context = swe_models.SweContext(plan=plan, swe_summary="summary")
    kb = SweKnowledgeBase(
        ground_data_dir="/tmp/ground",
        linked_data_dir="/tmp/linked",
    )
    server_context = SweServerContext(
        repo_root="repo",
        config=SweMcpConfig(),
        kb=kb,
        templates=[{"name": "template"}],
    )

    assert isinstance(context, swe_models.SweContext)
    assert server_context.repo_root == "repo"
    assert server_context.templates == [{"name": "template"}]


def test_read_file_reads_utf8_content(tmp_path):
    sample = tmp_path / "sample.txt"
    sample.write_text("hello world", encoding="utf-8")

    assert read_file(str(sample)) == "hello world"


@pytest.mark.asyncio
async def test_judge_code_changes_step_run_returns_explanation(monkeypatch):
    class FakeKnowledgeBase:
        def __init__(self):
            self.loaded = False

        def load(self):
            self.loaded = True

    class FakeExplanationService:
        def __init__(self, kb, llm_client, config):
            self.kb = kb
            self.llm_client = llm_client
            self.config = config

        def explain_change(self, swe_context, original_code, modified_code):
            return SweCodeChangeExplanation(
                plan=swe_context.plan,
                overall_verdict="acceptable",
                confidence=0.9,
                rationale=f"{original_code}->{modified_code}",
                nfr_impacts=[],
                risks=[],
                recommended_tests=["pytest"],
            )

    monkeypatch.setattr(judge_module, "ExplanationService", FakeExplanationService)

    kb = FakeKnowledgeBase()
    tool = JudgeCodeChangesStep(kb=kb, llm_client=object())
    context = SweContext(
        plan=CodeGenPlan(problem_description="Explain a code change"),
        swe_summary="summary",
    )

    response = await tool.run(
        swe_context=context,
        original_code="before",
        modified_code="after",
    )

    assert kb.loaded is True
    assert response.overall_verdict == "acceptable"
    assert response.rationale == "before->after"
    assert response.recommended_tests == ["pytest"]
