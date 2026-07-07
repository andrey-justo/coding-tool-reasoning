import json
from types import SimpleNamespace

import pytest

from src.mcp.swe_mcp_server import SweMcpServerContextProvider
from src.mcp.tools import judge_code_changes_step as judge_module
from src.mcp.tools import swe_mcp_tools as swe_tools_module
from src.mcp.tools.judge_code_changes_step import JudgeCodeChangesStep
from src.mcp.tools.swe_mcp_tools import register_swe_mcp_tools
from src.models import swe_models
from src.models.code_gen_plan import CodeGenPlan
from src.models.swe_config import SweMcpConfig
from src.models.swe_context import SweContext
from src.models.swe_edge import SweEdge
from src.models.swe_explanation import SweCodeChangeExplanation
from src.models.swe_node import SweNode
from src.models.swe_server_context import SweServerContext
from src.service.intent_planner import IntentPlanner
from src.service.swe_knowledge_base_service import SweKnowledgeBase
from src.utils.file_reader import read_file


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
    ground_dir = tmp_path / "knowledge" / "data"
    linked_dir = tmp_path / "knowledge bases" / "linked_data"
    item_dir = ground_dir / "reliability" / "retry_logic"
    item_dir.mkdir(parents=True)
    linked_dir.mkdir(parents=True)

    (item_dir / "data.json").write_text(
        json.dumps(
            {
                "name": "Retry Logic",
                "problem": "Retries transient failures to improve resilience.",
            }
        ),
        encoding="utf-8",
    )
    (linked_dir / "edges.csv").write_text(
        "SourceId,Relation,TargetId,Description\n"
        "nfr_reliability,related_to,pattern_retry_logic,Supports reliability\n",
        encoding="utf-8",
    )

    kb = SweKnowledgeBase(
        ground_data_dir=str(ground_dir),
        linked_data_dir=str(linked_dir),
    )
    kb.load()

    assert kb.find_nfr_ids(["Reliability"]) == ["nfr_reliability"]
    assert (
        kb.get_neighbors(["nfr_reliability"])["nfr_reliability"][0].target_id
        == "pattern_retry_logic"
    )
    assert "nfr_reliability" in [node.id for node in kb.get_all_nfrs()]

    summary = kb.summarize_for_prompt(["nfr_reliability"], depth=1)
    assert "NFR: Reliability" in summary
    assert "related_to: Retry Logic" in summary


def test_swe_knowledge_base_load_is_idempotent(tmp_path):
    ground_dir = tmp_path / "knowledge bases" / "ground_data"
    linked_dir = tmp_path / "knowledge bases" / "linked_data"
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
    ground_dir = tmp_path / "knowledge bases" / "ground_data"
    linked_dir = tmp_path / "knowledge bases" / "linked_data"
    ground_dir.mkdir(parents=True)
    linked_dir.mkdir(parents=True)

    (ground_dir / "nodes.csv").write_text(
        "# knowledge base nodes\n"
        "\n"
        "Id,Type,Name,NFRCategory,Description\n"
        "\n"
        "# section break\n"
        "NFR-1,NFR,Reliability,Reliability,Improves uptime\n",
        encoding="utf-8",
    )
    (linked_dir / "edges.csv").write_text(
        "# knowledge base edges\n"
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
    assert default_config.knowledge_base.relationship_depth == 1

    config_path = tmp_path / "swe_mcp_config.yaml"
    config_path.write_text(
        json.dumps(
            {
                "knowledge_base": {"relationship_depth": 2},
                "planning": {"max_steps": 3},
                "judging": {"max_risks": 2},
            }
        ),
        encoding="utf-8",
    )

    loaded_config = SweMcpConfig.load(str(tmp_path))
    assert loaded_config.knowledge_base.relationship_depth == 2
    assert loaded_config.planning.max_steps == 3
    assert loaded_config.judging.max_risks == 2

    config_path.write_text("not: [valid", encoding="utf-8")

    fallback_config = SweMcpConfig.load(str(tmp_path))
    assert fallback_config.knowledge_base.relationship_depth == 1


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


def test_build_swe_code_context_writes_prompt_assets(tmp_path):
    class FakeMCP:
        def __init__(self):
            self.tools = {}

        def tool(self):
            def decorator(func):
                self.tools[func.__name__] = func
                return func

            return decorator

    class FakeKnowledgeBase:
        def find_nfr_ids(self, nfr_focus):
            return ["NFR-1"] if nfr_focus else []

        def summarize_for_prompt(self, nfr_ids):
            if not nfr_ids:
                return "No NFR focus"
            return "NFR: Reliability"

    fake_ctx = SimpleNamespace(
        repo_root=str(tmp_path),
        kb=FakeKnowledgeBase(),
        templates=[
            {
                "kind": "swe_concern_template",
                "name": "base_template",
                "content": "Template body",
            }
        ],
    )

    mcp = FakeMCP()
    register_swe_mcp_tools(mcp, lambda: fake_ctx)

    build_context = mcp.tools["build_swe_code_context"]
    plan = CodeGenPlan(
        problem_description="Refactor authentication flow",
        nfr_focus=["Reliability"],
    )

    result = build_context(
        plan=plan,
        include_templates=True,
        security_extra_context="Security notes",
        prompt_output_folder="generated/prompts",
    )

    assert isinstance(result, SweContext)
    assert result.swe_summary == "NFR: Reliability"
    assert len(result.templates) == 1

    generated_root = tmp_path / "generated" / "prompts"
    run_dirs = [d for d in generated_root.iterdir() if d.is_dir()]
    assert len(run_dirs) == 1

    run_dir = run_dirs[0]
    assert (run_dir / "plan.json").exists()
    assert (run_dir / "swe_summary.md").exists()
    assert (run_dir / "prompt_context.md").exists()

    templates_dir = run_dir / "templates"
    assert templates_dir.exists()
    template_files = list(templates_dir.glob("*.md"))
    assert len(template_files) == 1


def test_intent_planner_infers_target_language_when_missing():
    kb = SweKnowledgeBase(
        ground_data_dir="/tmp/ground",
        linked_data_dir="/tmp/linked",
    )
    kb.nodes = {
        "NFR-1": SweNode(
            id="NFR-1",
            type="NFR",
            name="Maintainability",
            nfr_category="Maintainability",
            description="Readable and easy to change",
        )
    }
    kb.edges = []

    class FakeLLMClient:
        def chat(self, prompt):
            return '{"high_level_steps": ["Refactor module boundaries"]}'

    planner = IntentPlanner(kb=kb, llm_client=FakeLLMClient(), config=SweMcpConfig())

    result = planner.plan(
        problem_description="Refactor this Python service and improve maintainability"
    )

    assert result.inferred_target_language == "python"
    assert result.high_level_steps == ["Refactor module boundaries"]


def test_intent_planner_expands_nfr_intents_via_knowledge_base_loop():
    kb = SweKnowledgeBase(
        ground_data_dir="/tmp/ground",
        linked_data_dir="/tmp/linked",
    )
    kb.nodes = {
        "NFR-1": SweNode(
            id="NFR-1",
            type="NFR",
            name="Maintainability",
            nfr_category="Maintainability",
            description="",
        ),
        "NFR-2": SweNode(
            id="NFR-2",
            type="NFR",
            name="Reliability",
            nfr_category="Reliability",
            description="",
        ),
        "NFR-3": SweNode(
            id="NFR-3",
            type="NFR",
            name="Security",
            nfr_category="Security",
            description="",
        ),
    }
    kb.edges = [
        SweEdge(
            source_id="NFR-1",
            relation="supports",
            target_id="NFR-2",
            description="",
        ),
        SweEdge(
            source_id="NFR-2",
            relation="related_to",
            target_id="NFR-3",
            description="",
        ),
    ]

    config = SweMcpConfig()
    config.planning.max_intent_inference_loops = 2

    class FakeLLMClient:
        def chat(self, prompt):
            return '{"high_level_steps": ["Analyze dependencies"]}'

    planner = IntentPlanner(kb=kb, llm_client=FakeLLMClient(), config=config)
    result = planner.plan(problem_description="Improve maintainability")

    assert "Maintainability" in result.nfr_focus
    assert "Reliability" in result.nfr_focus
    assert "Security" in result.nfr_focus
    assert set(result.resolved_nfr_ids) == {"NFR-1", "NFR-2", "NFR-3"}


def test_intent_planner_includes_user_prompt_data_in_llm_prompt():
    kb = SweKnowledgeBase(
        ground_data_dir="/tmp/ground",
        linked_data_dir="/tmp/linked",
    )
    kb.nodes = {
        "NFR-1": SweNode(
            id="NFR-1",
            type="NFR",
            name="Maintainability",
            nfr_category="Maintainability",
            description="",
        )
    }
    kb.edges = []

    captured = {"prompt": ""}

    class FakeLLMClient:
        def chat(self, prompt):
            captured["prompt"] = prompt
            return '{"high_level_steps": ["Do planning"]}'

    planner = IntentPlanner(kb=kb, llm_client=FakeLLMClient(), config=SweMcpConfig())
    planner.plan(
        problem_description="Improve maintainability",
        user_prompt_data="Repository has strict API backward compatibility constraints.",
    )

    assert "Additional user prompt data" in captured["prompt"]
    assert "strict API backward compatibility constraints" in captured["prompt"]


def test_class_based_tool_registry_plan_and_build(monkeypatch, tmp_path):
    class FakeKnowledgeBase:
        def find_nfr_ids(self, nfr_focus):
            return ["NFR-1"] if nfr_focus else []

        def summarize_for_prompt(self, nfr_ids):
            return "NFR summary"

    fake_ctx = SimpleNamespace(
        repo_root=str(tmp_path),
        kb=FakeKnowledgeBase(),
        templates=[{"name": "base_template", "content": "Template body"}],
        config=SweMcpConfig(),
    )

    class FakePlanner:
        def __init__(self, kb, config):
            self.kb = kb
            self.config = config

        def plan(
            self, problem_description, target_language, nfr_focus, user_prompt_data
        ):
            return SimpleNamespace(
                inferred_target_language=target_language or "python",
                nfr_focus=nfr_focus or ["Maintainability"],
                high_level_steps=["Step A"],
                resolved_nfr_ids=["NFR-1"],
            )

    registry = swe_tools_module.SweMcpToolRegistry(
        lambda: fake_ctx,
        planner_cls=FakePlanner,
    )
    plan = registry.plan_swe_code_change(
        problem_description="Refactor auth service",
        target_language=None,
        nfr_focus=["Reliability"],
        user_prompt_data="focus on backward compatibility",
    )

    assert plan.target_language == "python"
    assert plan.high_level_steps == ["Step A"]

    context = registry.build_swe_code_context(
        plan=plan,
        include_templates=True,
        prompt_output_folder="generated/prompts",
    )
    assert isinstance(context, SweContext)
    assert context.swe_summary == "NFR summary"


def test_server_context_provider_loads_concern_assets(monkeypatch, tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir(parents=True)

    templates_dir = repo_root / "knowledge" / "template"
    templates_dir.mkdir(parents=True)
    (templates_dir / "base_template.md").write_text(
        "Template content", encoding="utf-8"
    )

    data_dir = repo_root / "knowledge" / "data" / "reliability" / "group_a"
    data_dir.mkdir(parents=True)
    (data_dir / "data.json").write_text('{"name": "group_a"}', encoding="utf-8")

    config = SweMcpConfig()

    class FakeKnowledgeBase:
        def __init__(self, ground_data_dir, linked_data_dir, lazy_load_nodes=False):
            self.ground_data_dir = ground_data_dir
            self.linked_data_dir = linked_data_dir
            self.lazy_load_nodes = lazy_load_nodes

        def load(self):
            return None

    monkeypatch.setattr(
        "src.mcp.swe_mcp_server.SweMcpConfig.load", lambda repo_root: config
    )
    monkeypatch.setattr("src.mcp.swe_mcp_server.SweKnowledgeBase", FakeKnowledgeBase)

    provider = SweMcpServerContextProvider(repo_root=str(repo_root))
    ctx = provider.create_swe_server_context(force_reload=True)

    kinds = {item["kind"] for item in ctx.templates}
    assert "swe_concern_template" in kinds
    assert "swe_concern_data" in kinds
    assert ctx.kb.ground_data_dir.replace("\\", "/").endswith("knowledge/data")
    assert ctx.kb.linked_data_dir.replace("\\", "/").endswith("knowledge/linked_data")

    data_items = [item for item in ctx.templates if item["kind"] == "swe_concern_data"]
    assert len(data_items) == 1
    assert '"DESIGN_PATTERN_NAME": "group_a"' in data_items[0]["content"]

