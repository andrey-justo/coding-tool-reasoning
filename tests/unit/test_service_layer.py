import json

from src.models.code_gen_plan import CodeGenPlan
from src.models.swe_config import SweMcpConfig
from src.models.swe_context import SweContext
from src.models.swe_edge import SweEdge
from src.models.swe_node import SweNode
from src.service.explanation_service import ExplanationService
from src.service.intent_planner import IntentPlanner
from src.service.swe_taxonomy_service import SweKnowledgeBase


def _build_minimal_kb() -> SweKnowledgeBase:
    kb = SweKnowledgeBase(ground_data_dir="/tmp/ground", linked_data_dir="/tmp/linked")
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
    return kb


def test_intent_planner_falls_back_to_default_steps_on_invalid_llm_json():
    class FakeLLMClient:
        def chat(self, prompt):
            return "this is not json"

    planner = IntentPlanner(
        kb=_build_minimal_kb(), llm_client=FakeLLMClient(), config=SweMcpConfig()
    )
    result = planner.plan(problem_description="Improve maintainability")

    assert len(result.high_level_steps) == 6
    assert "Understand the current behavior" in result.high_level_steps[0]


def test_intent_planner_truncates_llm_steps_to_configured_max_steps():
    class FakeLLMClient:
        def chat(self, prompt):
            return json.dumps(
                {
                    "high_level_steps": [
                        "Step 1",
                        "Step 2",
                        "Step 3",
                        "Step 4",
                    ]
                }
            )

    config = SweMcpConfig()
    config.planning.max_steps = 2

    planner = IntentPlanner(
        kb=_build_minimal_kb(), llm_client=FakeLLMClient(), config=config
    )
    result = planner.plan(problem_description="Improve maintainability")

    assert result.high_level_steps == ["Step 1", "Step 2"]


def test_intent_planner_can_disable_language_inference():
    class FakeLLMClient:
        def chat(self, prompt):
            return '{"high_level_steps": ["Do work"]}'

    config = SweMcpConfig()
    config.planning.infer_target_language_when_missing = False

    planner = IntentPlanner(
        kb=_build_minimal_kb(), llm_client=FakeLLMClient(), config=config
    )
    result = planner.plan(problem_description="Refactor this Python API")

    assert result.inferred_target_language is None


def test_explanation_service_parses_impacts_and_limits_risks():
    class FakeKB:
        def find_nfr_ids(self, nfr_focus):
            return ["NFR-1"] if nfr_focus else []

        def summarize_for_prompt(self, nfr_ids, depth=1):
            return "taxonomy"

    class FakeLLMClient:
        def chat(self, prompt):
            return json.dumps(
                {
                    "overall_verdict": "acceptable",
                    "rationale": "Change aligns with plan",
                    "nfr_impacts": [
                        {
                            "nfr": "Maintainability",
                            "verdict": "improved",
                            "reasoning": "Reduced duplication",
                        },
                        "invalid-item",
                    ],
                    "risks": ["risk-1", "risk-2", "risk-3"],
                    "recommended_tests": ["", "unit test auth service"],
                }
            )

    config = SweMcpConfig()
    config.judging.max_risks = 2

    plan = CodeGenPlan(
        problem_description="Refactor auth service",
        nfr_focus=["Maintainability"],
        high_level_steps=["Step 1"],
    )
    context = SweContext(plan=plan, swe_summary="summary")

    service = ExplanationService(kb=FakeKB(), llm_client=FakeLLMClient(), config=config)
    explanation = service.explain_change(
        swe_context=context,
        original_code="before",
        modified_code="after",
    )

    assert explanation.overall_verdict == "acceptable"
    assert len(explanation.nfr_impacts) == 1
    assert explanation.nfr_impacts[0].nfr == "Maintainability"
    assert explanation.risks == ["risk-1", "risk-2"]
    assert explanation.recommended_tests == ["unit test auth service"]


def test_explanation_service_uses_fallback_when_llm_response_is_invalid():
    class FakeKB:
        def find_nfr_ids(self, nfr_focus):
            return []

        def summarize_for_prompt(self, nfr_ids, depth=1):
            return "taxonomy"

    class FakeLLMClient:
        def chat(self, prompt):
            return "not-a-json-payload"

    plan = CodeGenPlan(
        problem_description="Refactor auth service",
        high_level_steps=["Step 1"],
    )
    context = SweContext(plan=plan, swe_summary="summary")

    service = ExplanationService(
        kb=FakeKB(), llm_client=FakeLLMClient(), config=SweMcpConfig()
    )
    explanation = service.explain_change(
        swe_context=context,
        original_code="before",
        modified_code="after",
    )

    assert explanation.overall_verdict == "manual-review-required"
    assert explanation.risks
    assert "Automated explanation failed" in explanation.risks[0]


def test_swe_knowledge_base_find_nfr_ids_matches_by_id_name_and_category_case_insensitive():
    kb = SweKnowledgeBase(ground_data_dir="/tmp/ground", linked_data_dir="/tmp/linked")
    kb.nodes = {
        "NFR-1": SweNode(
            id="NFR-1",
            type="NFR",
            name="Maintainability",
            nfr_category="Code Quality",
            description="",
        ),
        "NFR-2": SweNode(
            id="NFR-2",
            type="NFR",
            name="Reliability",
            nfr_category="Reliability",
            description="",
        ),
        "PRA-1": SweNode(
            id="PRA-1",
            type="Practice",
            name="Retry Logic",
            nfr_category="Reliability",
            description="",
        ),
    }

    resolved = kb.find_nfr_ids(["nfr-1", "reliability", "CODE QUALITY"])

    assert set(resolved) == {"NFR-1", "NFR-2"}


def test_swe_knowledge_base_summary_depth_controls_expansion():
    kb = SweKnowledgeBase(ground_data_dir="/tmp/ground", linked_data_dir="/tmp/linked")
    kb.nodes = {
        "NFR-1": SweNode(
            id="NFR-1",
            type="NFR",
            name="Reliability",
            nfr_category="Reliability",
            description="Root",
        ),
        "PRA-1": SweNode(
            id="PRA-1",
            type="Practice",
            name="Retry Logic",
            nfr_category="Reliability",
            description="Practice",
        ),
        "SMELL-1": SweNode(
            id="SMELL-1",
            type="Smell",
            name="Long Method",
            nfr_category="Maintainability",
            description="Smell",
        ),
    }
    kb.edges = [
        SweEdge(
            source_id="NFR-1",
            relation="related_to",
            target_id="PRA-1",
            description="nfr to practice",
        ),
        SweEdge(
            source_id="PRA-1",
            relation="avoids",
            target_id="SMELL-1",
            description="practice to smell",
        ),
    ]

    summary_depth_1 = kb.summarize_for_prompt(["NFR-1"], depth=1)
    summary_depth_2 = kb.summarize_for_prompt(["NFR-1"], depth=2)

    assert "related_to: Retry Logic" in summary_depth_1
    assert "Long Method" not in summary_depth_1
    assert "Long Method" in summary_depth_2
