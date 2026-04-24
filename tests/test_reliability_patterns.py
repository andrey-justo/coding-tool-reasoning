import builtins
import io
import json
from types import SimpleNamespace

import pytest
import requests

from src.errors.TextLLMException import TextLLMException
from src.business_logic.explanation_service import ExplanationService
from src.evaluation import reliability_evaluation as reliability_eval_module
from src.evaluation.reliability_evaluation import ReliabilityEvaluationTool
from src.llm_client import multi_model_llm_client as multi_model_module
from src.llm_client.localai_client import LocalAIClient
from src.llm_client.multi_model_llm_client import MultiModelLLMClient
from src.models.code_gen_plan import CodeGenPlan
from src.models.swe_config import SweMcpConfig
from src.models.swe_context import SweContext
from src.tools.reliability_design import ReliabilityDesignTool


class DummyTensor:
    def __init__(self, value):
        self._value = value

    def item(self):
        return self._value


class FakeBERTScorer:
    def __init__(self, *args, **kwargs):
        pass

    def score(self, generated, reference):
        assert len(generated) == 1
        assert len(reference) == 1
        return [DummyTensor(0.9)], [DummyTensor(0.8)], [DummyTensor(0.85)]


def test_reliability_evaluator_extracts_csharp_and_scores(monkeypatch):
    monkeypatch.setattr(reliability_eval_module, "BERTScorer", FakeBERTScorer)
    evaluator = ReliabilityEvaluationTool()

    code = evaluator.extract_csharp_code("before ```csharp\nclass A {}\n``` after")
    assert code == "class A {}"

    extracted = evaluator.extract_code_from_agent_response("```csharp\nclass B {}\n```")
    assert extracted == "class B {}"

    scores = evaluator.evaluate("class B {}", "class Ref {}")
    assert scores == {"precision": 0.9, "recall": 0.8, "f1": 0.85}


def test_localai_client_chat_success(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"content": "ok"}}]}

    class FakeSession:
        def post(self, *args, **kwargs):
            return FakeResponse()

    client = LocalAIClient(
        endpoint="http://localhost:8080", default_model="m1", api_key="token"
    )
    monkeypatch.setattr(client, "session", FakeSession())

    assert client._headers()["Authorization"] == "token"
    assert client.chat("hello") == "ok"


def test_localai_client_timeout_is_wrapped(monkeypatch):
    class TimeoutSession:
        def post(self, *args, **kwargs):
            raise requests.exceptions.Timeout("timed out")

    client = LocalAIClient(endpoint="http://localhost:8080", default_model="m1")
    monkeypatch.setattr(client, "session", TimeoutSession())

    with pytest.raises(TextLLMException):
        client.chat("hello")


@pytest.mark.parametrize(
    "raised",
    [
        requests.exceptions.ConnectionError("conn"),
        requests.exceptions.RequestException("req"),
        RuntimeError("unexpected"),
    ],
)
def test_localai_client_other_errors_are_wrapped(monkeypatch, raised):
    class ErrorSession:
        def post(self, *args, **kwargs):
            raise raised

    client = LocalAIClient(endpoint="http://localhost:8080", default_model="m1")
    monkeypatch.setattr(client, "session", ErrorSession())

    with pytest.raises(TextLLMException):
        client.chat("hello")


def test_multi_model_client_dispatch_for_single_and_multiple_models():
    class FakeClient:
        def __init__(self, name):
            self.name = name

        def chat(self, prompt, **kwargs):
            return f"{self.name}:{prompt}"

    client = MultiModelLLMClient.__new__(MultiModelLLMClient)
    client.default_model = "m1"
    client.clients = {"m1": FakeClient("m1"), "m2": FakeClient("m2")}

    assert client.get_client().name == "m1"
    assert client.chat("ping") == "m1:ping"
    assert client.chat("ping", model=["m1", "m2"]) == {
        "m1": "m1:ping",
        "m2": "m2:ping",
    }

    with pytest.raises(ValueError):
        client.get_client("unknown")


def test_multi_model_client_init_builds_clients_with_and_without_api_key(monkeypatch):
    created = {"local": []}

    class FakeLocalClient:
        def __init__(self, **kwargs):
            created["local"].append(kwargs)

    model_config = [
        {"model_name": "local-model", "provider": "LocalAI", "endpoint": "http://localhost:8080"},
        {"model_name": "backup-model", "provider": "LocalAI", "endpoint": "http://localhost:8081"},
    ]

    monkeypatch.setattr(multi_model_module, "LocalAIClient", FakeLocalClient)
    monkeypatch.setattr(multi_model_module.yaml, "safe_load", lambda _: model_config)

    original_open = builtins.open

    def fake_open(path, *args, **kwargs):
        if str(path).endswith("available_models.yaml"):
            return io.StringIO("models: []")
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", fake_open)

    def load_env_with_key(self):
        self.api_key = "token"
        self.default_model = "local-model"

    monkeypatch.setattr(MultiModelLLMClient, "load_env", load_env_with_key)
    client_with_key = MultiModelLLMClient()
    assert "local-model" in client_with_key.clients
    assert "backup-model" in client_with_key.clients
    assert created["local"][0]["api_key"] == "token"

    created["local"].clear()

    def load_env_without_key(self):
        self.api_key = None
        self.default_model = "local-model"

    monkeypatch.setattr(MultiModelLLMClient, "load_env", load_env_without_key)
    client_without_key = MultiModelLLMClient()
    assert set(client_without_key.clients.keys()) == {"local-model", "backup-model"}
    assert created["local"][0]["api_key"] is None


def test_multi_model_client_init_rejects_azure_provider(monkeypatch):
    model_config = [
        {
            "model_name": "azure-model",
            "provider": "AzureOpenAI",
            "endpoint": "https://x",
            "api_version": "2024-02-15-preview",
        }
    ]

    monkeypatch.setattr(multi_model_module.yaml, "safe_load", lambda _: model_config)

    original_open = builtins.open

    def fake_open(path, *args, **kwargs):
        if str(path).endswith("available_models.yaml"):
            return io.StringIO("models: []")
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", fake_open)
    monkeypatch.setattr(
        MultiModelLLMClient,
        "load_env",
        lambda self: setattr(self, "default_model", "azure-model") or setattr(self, "api_key", None),
    )

    with pytest.raises(ValueError, match="AzureOpenAI provider is not supported"):
        MultiModelLLMClient()


def test_multi_model_client_load_env_reads_variables(monkeypatch):
    client = MultiModelLLMClient.__new__(MultiModelLLMClient)
    client.api_key = None
    client.default_model = None

    monkeypatch.setattr(multi_model_module.os.path, "exists", lambda _: True)
    monkeypatch.setattr(multi_model_module, "load_dotenv", lambda _: None)

    values = {"API_KEY": "abc", "DEFAULT_MODEL": "local-model"}
    monkeypatch.setattr(multi_model_module.os, "getenv", lambda key: values.get(key))

    client.load_env()
    assert client.api_key == "abc"
    assert client.default_model == "local-model"


def test_explanation_service_parses_llm_json_and_limits_risks():
    captured = {"prompt": None}

    class FakeKnowledgeBase:
        def find_nfr_ids(self, names):
            assert names == ["Reliability"]
            return ["NFR-1"]

        def summarize_for_prompt(self, node_ids, depth=1):
            assert node_ids == ["NFR-1"]
            assert depth == 2
            return "taxonomy summary"

    class FakeLLMClient:
        def chat(self, prompt):
            captured["prompt"] = prompt
            return json.dumps(
                {
                    "overall_verdict": "acceptable",
                    "rationale": "The change follows the plan.",
                    "nfr_impacts": [
                        object(),
                        {
                            "nfr": "Reliability",
                            "verdict": "improved",
                            "reasoning": "Retry logic reduces transient failures.",
                        },
                    ],
                    "risks": ["risk-1", "risk-2"],
                    "recommended_tests": ["pytest -q"],
                },
                default=str,
            )

    config = SweMcpConfig()
    config.taxonomy.relationship_depth = 2
    config.judging.strictness = 0.8
    config.judging.max_risks = 1

    service = ExplanationService(
        kb=FakeKnowledgeBase(),
        llm_client=FakeLLMClient(),
        config=config,
    )
    context = SweContext(
        plan=CodeGenPlan(
            problem_description="Add retry logic",
            nfr_focus=["Reliability"],
            high_level_steps=["Add retries", "Update tests"],
        ),
        swe_summary="summary",
        security_context="threat model",
    )

    response = service.explain_change(
        swe_context=context,
        original_code="before",
        modified_code="after",
    )

    assert response.overall_verdict == "acceptable"
    assert response.risks == ["risk-1"]
    assert response.nfr_impacts[0].nfr == "Reliability"
    assert response.recommended_tests == ["pytest -q"]
    assert "Judging strictness (0-1): 0.80 (strict)." in captured["prompt"]
    assert "Additional Security Context" in captured["prompt"]


def test_explanation_service_falls_back_when_llm_output_is_not_json():
    class FakeKnowledgeBase:
        def find_nfr_ids(self, names):
            return ["NFR-1"]

        def summarize_for_prompt(self, node_ids, depth=1):
            return "taxonomy summary"

    class FakeLLMClient:
        def chat(self, prompt):
            return "not-json"

    service = ExplanationService(kb=FakeKnowledgeBase(), llm_client=FakeLLMClient())
    context = SweContext(
        plan=CodeGenPlan(problem_description="Explain change"),
        swe_summary="summary",
    )

    response = service.explain_change(
        swe_context=context,
        original_code="before",
        modified_code="after",
    )

    assert response.overall_verdict == "manual-review-required"
    assert response.risks
    assert response.recommended_tests


def test_reliability_design_helper_methods_use_prompt_templates(tmp_path):
    prompts = []

    class FakeLLMClient:
        def chat(self, prompt, model=None):
            prompts.append(prompt)
            return '{"selected_design_pattern": "circuit_breaker"}'

    tool = ReliabilityDesignTool(llm_client=FakeLLMClient())
    tool.extract_prompt_path = str(tmp_path / "extract_reliability_input.md")
    tool.identify_prompt_path = str(tmp_path / "identify_reliability_design.md")
    (tmp_path / "extract_reliability_input.md").write_text(
        "extract: {{input}}", encoding="utf-8"
    )
    (tmp_path / "identify_reliability_design.md").write_text(
        "identify: {{input}}", encoding="utf-8"
    )

    extracted = tool.extract_input("please add reliability")
    identified = tool.identify_design("circuit_breaker")

    assert extracted == {"llm_response": '{"selected_design_pattern": "circuit_breaker"}'}
    assert identified == '{"selected_design_pattern": "circuit_breaker"}'
    assert prompts == [
        "extract: please add reliability",
        "identify: circuit_breaker",
    ]

    assert tool._parse_to_dict('{"x": "y"}', "x") == {"x": "y"}
    assert tool._parse_to_dict("plain", "x") == {"x": "plain"}
    assert tool.get_raw_response(SimpleNamespace(value=1)).startswith("namespace(")


@pytest.mark.asyncio
async def test_reliability_design_run_happy_path(monkeypatch):
    tool = ReliabilityDesignTool(llm_client=object())

    monkeypatch.setattr(
        tool,
        "extract_input",
        lambda message, models=None: {"selected_design_pattern": "circuit breaker"},
    )
    monkeypatch.setattr(tool, "identify_design", lambda name, models=None: "circuit_breaker")
    monkeypatch.setattr(
        tool,
        "select_and_execute_template",
        lambda pattern, models=None: f"generated:{pattern}",
    )

    response = await tool.run(messages="please add reliability")

    assert response == "generated:circuit_breaker"


def test_reliability_design_select_and_execute_template_paths(tmp_path, monkeypatch):
    class FakeLLMClient:
        def chat(self, prompt, model=None):
            return "final-code"

    tool = ReliabilityDesignTool(llm_client=FakeLLMClient())
    tool.add_design_pattern_template = str(tmp_path / "base_template.md")
    tool.tests_template = str(tmp_path / "tests_template.md")
    (tmp_path / "base_template.md").write_text("pattern: {{name}}", encoding="utf-8")
    (tmp_path / "tests_template.md").write_text("tests", encoding="utf-8")
    tool.read_templates()

    monkeypatch.chdir(tmp_path)
    pattern_dir = tmp_path / "templates" / "reliability" / "circuit_breaker"
    pattern_dir.mkdir(parents=True)
    (pattern_dir / "base_design.json").write_text(
        json.dumps({"name": "circuit_breaker"}), encoding="utf-8"
    )

    assert tool.select_and_execute_template("circuit_breaker") == "final-code"


def test_reliability_design_select_and_execute_template_falls_back_to_base_template(
    tmp_path,
):
    captured = {"prompt": None}

    class FakeLLMClient:
        def chat(self, prompt, model=None):
            captured["prompt"] = prompt
            return "fallback-code"

    tool = ReliabilityDesignTool(llm_client=FakeLLMClient())
    tool.add_design_pattern_template = str(tmp_path / "base_template.md")
    tool.tests_template = str(tmp_path / "tests_template.md")
    (tmp_path / "base_template.md").write_text(
        "pattern: {{design_pattern_name}}", encoding="utf-8"
    )
    (tmp_path / "tests_template.md").write_text("tests", encoding="utf-8")
    tool.read_templates()

    result = tool.select_and_execute_template("missing pattern")

    assert result == "fallback-code"
    assert captured["prompt"] == "pattern: missing pattern"
