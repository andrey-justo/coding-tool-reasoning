import json
import logging
from pathlib import Path

import pytest

from src.mcp.swe_mcp_server import SweMcpServerContextProvider
from src.mcp.tools.swe_mcp_tools import SweMcpToolRegistry
from src.models.code_gen_plan import CodeGenPlan
from src.models.swe_config import SweMcpConfig
from src.service.intent_planner import IntentPlanner
from tests.smoke.conftest import (
    DEFAULT_SMOKE_PROMPT_LOG_DIR,
    REPO_ROOT,
    reset_output_root,
    resolve_prompt_output_root,
)

# ---------------------------------------------------------------------------
# Fixture data directory â€“ all test inputs live here; nothing is hardcoded.
# ---------------------------------------------------------------------------
TEST_DATA_DIR = Path(__file__).parent / "data"


def _discover_test_data_files() -> list[Path]:
    """Discover all .json test data files in tests/smoke/data/."""
    if not TEST_DATA_DIR.exists():
        return []
    return sorted(TEST_DATA_DIR.glob("*_smoke_test.json"))


def _load_test_data(test_file: Path) -> dict:
    """Load test data from a JSON file."""
    return json.loads(test_file.read_text(encoding="utf-8"))


class _FakeLlmClient:
    def chat(self, prompt: str) -> str:
        return json.dumps({"high_level_steps": ["Inspect related NFR trade-offs"]})


class _PlannerWithFakeLlm(IntentPlanner):
    def __init__(self, kb, config):
        super().__init__(kb=kb, llm_client=_FakeLlmClient(), config=config)


@pytest.fixture
def robust_smoke_log_file(tmp_path, request):
    """Attach a per-test log handler without mutating global/root logging config."""

    log_dir = tmp_path / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"{request.node.name}.log"

    handler = logging.FileHandler(log_file, encoding="utf-8")
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
    )

    logger_names = [
        "src.mcp.tools.swe_mcp_tools",
        "src.service.swe_knowledge_base_service",
        "src.service.prompt_template_execution_service",
    ]

    managed_loggers = []
    for logger_name in logger_names:
        logger = logging.getLogger(logger_name)
        managed_loggers.append((logger, logger.level))
        logger.addHandler(handler)
        if logger.level == logging.NOTSET or logger.level > logging.INFO:
            logger.setLevel(logging.INFO)

    try:
        yield log_file
    finally:
        for logger, previous_level in managed_loggers:
            logger.removeHandler(handler)
            logger.setLevel(previous_level)
        handler.close()


@pytest.mark.parametrize("test_data_file", _discover_test_data_files())
def test_robust_prompt_smoke_has_code_and_unit_test_examples(
    test_data_file,
    monkeypatch,
    robust_smoke_log_file,
):
    """Test robust smoke with code and unit test examples."""
    scenario = _load_test_data(test_data_file)
    subject = scenario["subject"]

    config = SweMcpConfig()
    config.concern_assets.swe_concern = "reliability"
    config.concern_assets.swe_subject = subject

    monkeypatch.setattr(
        "src.mcp.swe_mcp_server.SweMcpConfig.load",
        lambda repo_root: config,
    )

    provider = SweMcpServerContextProvider(repo_root=str(REPO_ROOT))
    registry = SweMcpToolRegistry(
        provider.create_swe_server_context,
        planner_cls=_PlannerWithFakeLlm,
    )

    plan = CodeGenPlan(
        problem_description=scenario["problem_description"],
        target_language=scenario["target_language"],
        nfr_focus=scenario["nfr_focus"],
        high_level_steps=scenario["high_level_steps"],
    )

    output_root = (
        resolve_prompt_output_root(
            "ROBUST_SMOKE_PROMPT_OUTPUT_DIR",
            DEFAULT_SMOKE_PROMPT_LOG_DIR,
        )
        / f"robust-smoke-{subject}"
    )
    reset_output_root(output_root)
    _context = registry.build_swe_code_context(
        plan=plan,
        include_templates=True,
        prompt_output_folder=str(output_root),
        write_executed_prompts=True,
    )

    run_dirs = [path for path in output_root.iterdir() if path.is_dir()]
    assert len(run_dirs) == 1
    executed_prompts = (run_dirs[0] / "executed_prompts.md").read_text(encoding="utf-8")

    # Requirement 1: code example included from the real repo example file.
    assert scenario["expectations"]["expected_code_snippet"] in executed_prompts

    # Requirement 2: unit-test prompt and example included when available.
    assert "Prompt 2: test_base_template" in executed_prompts
    assert scenario["expectations"]["expected_unit_test_snippet"] in executed_prompts

    robust_logs = robust_smoke_log_file.read_text(encoding="utf-8")
    assert "Building SWE code context" in robust_logs


@pytest.mark.parametrize("test_data_file", _discover_test_data_files())
def test_robust_prompt_smoke_skips_unit_test_template_when_example_missing(
    test_data_file,
    monkeypatch,
    robust_smoke_log_file,
):
    """Test robust smoke without unit test examples (negative path)."""
    scenario = _load_test_data(test_data_file)
    subject = scenario["subject"]

    # Save original load method before patching
    original_config_load = SweMcpConfig.load

    # Wrapper that strips UNIT_TEST_EXAMPLE from loaded concern data
    def load_config_without_unit_tests(repo_root):
        cfg = original_config_load(repo_root)
        cfg.concern_assets.swe_concern = "reliability"
        cfg.concern_assets.swe_subject = subject
        return cfg

    monkeypatch.setattr(
        "src.mcp.swe_mcp_server.SweMcpConfig.load",
        load_config_without_unit_tests,
    )

    # Also patch the provider's method to remove UNIT_TEST_EXAMPLE from concern data
    original_create_context = SweMcpServerContextProvider.create_swe_server_context

    def create_context_without_unit_tests(self, *args, **kwargs):
        context = original_create_context(self, *args, **kwargs)
        # Remove UNIT_TEST_EXAMPLE from templates' concern data
        for template in context.templates:
            if template.get("kind") == "swe_concern_data":
                try:
                    content_dict = json.loads(template.get("content", "{}"))
                    content_dict.pop("UNIT_TEST_EXAMPLE", None)
                    template["content"] = json.dumps(content_dict)
                except (json.JSONDecodeError, TypeError):
                    pass
        return context

    monkeypatch.setattr(
        SweMcpServerContextProvider,
        "create_swe_server_context",
        create_context_without_unit_tests,
    )

    provider = SweMcpServerContextProvider(repo_root=str(REPO_ROOT))
    registry = SweMcpToolRegistry(
        provider.create_swe_server_context,
        planner_cls=_PlannerWithFakeLlm,
    )

    plan = CodeGenPlan(
        problem_description=scenario["problem_description"],
        target_language=scenario["target_language"],
        nfr_focus=scenario["nfr_focus"],
        high_level_steps=scenario["high_level_steps"],
    )

    output_root = (
        resolve_prompt_output_root(
            "ROBUST_SMOKE_PROMPT_OUTPUT_DIR",
            DEFAULT_SMOKE_PROMPT_LOG_DIR,
        )
        / f"robust-smoke-no-tests-{subject}"
    )
    reset_output_root(output_root)
    _context = registry.build_swe_code_context(
        plan=plan,
        include_templates=True,
        prompt_output_folder=str(output_root),
        write_executed_prompts=True,
    )

    run_dirs = [path for path in output_root.iterdir() if path.is_dir()]
    assert len(run_dirs) == 1
    executed_prompts = (run_dirs[0] / "executed_prompts.md").read_text(encoding="utf-8")

    # Requirement 1: code example still included from the real repo example file.
    assert scenario["expectations"]["expected_code_snippet"] in executed_prompts

    # Negative path: unit-test prompt must be skipped.
    assert "Prompt 2: test_base_template" not in executed_prompts
    assert "Unit Test Template" not in executed_prompts

    robust_logs = robust_smoke_log_file.read_text(encoding="utf-8")
    assert "Skipping prompt template 'test_base_template'" in robust_logs

