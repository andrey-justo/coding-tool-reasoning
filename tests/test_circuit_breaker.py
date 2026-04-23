import pytest

from src.migration.analyzer import Analyzer
from src.migration.explainer import Explainer
from src.migration.prompt import Prompt
from src.ontology.entity import Entity
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


def test_entity_actions_append_and_return():
    entity = Entity(name="Supervisor", intent="Guide refactoring")
    entity.add_action("reviews", "Developer")

    actions = entity.get_actions()
    assert actions == [{"action": "reviews", "target": "Developer"}]


def test_read_file_reads_utf8_content(tmp_path):
    sample = tmp_path / "sample.txt"
    sample.write_text("hello world", encoding="utf-8")

    assert read_file(str(sample)) == "hello world"


@pytest.mark.asyncio
async def test_judge_code_changes_step_run_returns_empty_message():
    class DummyLLMClient:
        pass

    tool = JudgeCodeChangesStep(llm_client=DummyLLMClient())
    response = await tool.run(messages="test")

    assert response.messages == []
