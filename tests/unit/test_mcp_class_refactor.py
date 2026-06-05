from types import SimpleNamespace

from src.mcp.swe_mcp_server import SweMcpServerContextProvider
from src.mcp.tools.swe_mcp_tools import SweMcpToolRegistry, SweMcpToolsRegistrar
from src.models.swe_config import SweMcpConfig
from src.models.swe_context import SweContext


def test_tool_registry_direct_method_usage(tmp_path):
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

    registry = SweMcpToolRegistry(lambda: fake_ctx, planner_cls=FakePlanner)
    plan = registry.plan_swe_code_change(
        problem_description="Refactor auth service",
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
        def __init__(
            self, ground_data_dir, linked_data_dir, lazy_load_nodes=False
        ):
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
    assert isinstance(ctx.kb, FakeKnowledgeBase)
    assert ctx.kb.ground_data_dir.endswith("knowledge\\data")
    assert ctx.kb.linked_data_dir.endswith("knowledge\\linked_data")

    data_items = [item for item in ctx.templates if item["kind"] == "swe_concern_data"]
    assert len(data_items) == 1
    assert '"DESIGN_PATTERN_NAME": "group_a"' in data_items[0]["content"]


def test_tools_registrar_registers_expected_tool_names(tmp_path):
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
            return []

        def summarize_for_prompt(self, nfr_ids):
            return "summary"

    fake_ctx = SimpleNamespace(
        repo_root=str(tmp_path),
        kb=FakeKnowledgeBase(),
        templates=[],
        config=SweMcpConfig(),
    )

    mcp = FakeMCP()
    registrar = SweMcpToolsRegistrar(
        mcp=mcp,
        create_swe_server_context=lambda: fake_ctx,
    )
    registrar.register()

    assert "plan_swe_code_change" in mcp.tools
    assert "build_swe_code_context" in mcp.tools
    assert "judge_swe_code_change" in mcp.tools
