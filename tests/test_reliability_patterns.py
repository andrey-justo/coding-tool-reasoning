import json
import io
import builtins
from types import SimpleNamespace

import pytest
import requests

import src.evaluation.reliability_evaluation as reliability_eval_module
import src.llm_client.multi_model_llm_client as multi_model_module
from src.errors.TextLLMException import TextLLMException
from src.evaluation.reliability_evaluation import ReliabilityEvaluationTool
from src.llm_client.localai_client import LocalAIClient
from src.llm_client.multi_model_llm_client import MultiModelLLMClient
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

    response = SimpleNamespace(
        messages=[
            SimpleNamespace(
                contents=[SimpleNamespace(text="```csharp\nclass B {}\n```")]
            )
        ]
    )
    extracted = evaluator.extract_code_from_agent_response(response)
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

    client = LocalAIClient(endpoint="http://localhost:8080", default_model="m1", api_key="token")
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
    created = {"azure": [], "local": []}

    class FakeAzureClient:
        def __init__(self, **kwargs):
            created["azure"].append(kwargs)

    class FakeLocalClient:
        def __init__(self, **kwargs):
            created["local"].append(kwargs)

    class FakeCredential:
        pass

    model_config = [
        {"model_name": "azure-model", "provider": "AzureOpenAI", "endpoint": "https://x", "api_version": "2024-02-15-preview"},
        {"model_name": "local-model", "provider": "LocalAI", "endpoint": "http://localhost:8080"},
    ]

    monkeypatch.setattr(multi_model_module, "AzureOpenAIAssistantsClient", FakeAzureClient)
    monkeypatch.setattr(multi_model_module, "LocalAIClient", FakeLocalClient)
    monkeypatch.setattr(multi_model_module, "AzureCliCredential", FakeCredential)
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
    assert "azure-model" in client_with_key.clients
    assert "local-model" in client_with_key.clients
    assert created["azure"][0]["api_key"] == "token"

    created["azure"].clear()
    created["local"].clear()

    def load_env_without_key(self):
        self.api_key = None
        self.default_model = "local-model"

    monkeypatch.setattr(MultiModelLLMClient, "load_env", load_env_without_key)
    _ = MultiModelLLMClient()
    assert "credential" in created["azure"][0]


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


@pytest.mark.asyncio
async def test_reliability_design_run_happy_path(tmp_path):
    class FakeLLMClient:
        def chat(self, prompt, model=None):
            if "extract:" in prompt:
                return SimpleNamespace(
                    contents=[
                        SimpleNamespace(
                            text=json.dumps({"selected_design_pattern": "circuit breaker"})
                        )
                    ]
                )
            if "identify:" in prompt:
                return SimpleNamespace(
                    contents=[
                        SimpleNamespace(
                            text=json.dumps(
                                {"formatted_design_pattern_name": "circuit_breaker"}
                            )
                        )
                    ]
                )
            return SimpleNamespace(contents=[SimpleNamespace(text="generated")])

    extract_prompt = tmp_path / "extract_reliability_input.md"
    identify_prompt = tmp_path / "identify_reliability_design.md"
    base_template = tmp_path / "base_template.md"
    tests_template = tmp_path / "test_base_template.md"
    pattern_dir = tmp_path / "circuit_breaker"
    pattern_dir.mkdir()
    base_design = pattern_dir / "base_design.json"

    extract_prompt.write_text("extract: {{input}}", encoding="utf-8")
    identify_prompt.write_text("identify: {{input}}", encoding="utf-8")
    base_template.write_text("pattern {{name}}", encoding="utf-8")
    tests_template.write_text("tests", encoding="utf-8")
    base_design.write_text(json.dumps({"name": "circuit_breaker"}), encoding="utf-8")

    tool = ReliabilityDesignTool(llm_client=FakeLLMClient())
    tool.extract_prompt_path = str(extract_prompt)
    tool.identify_prompt_path = str(identify_prompt)
    tool.add_design_pattern_template = str(base_template)
    tool.tests_template = str(tests_template)

    # Point template lookup to our temporary pattern directory.
    called = {"value": False}

    def fake_selector(design_pattern, models=None):
        called["value"] = True
        assert design_pattern == "circuit_breaker"
        return "generated"

    tool.select_and_execute_template = fake_selector

    response = await tool.run(messages="please add reliability")
    assert called["value"] is True
    assert response.messages == []


def test_reliability_design_select_and_execute_template_paths(tmp_path, monkeypatch):
    class FakeLLMClient:
        def chat(self, prompt, model=None):
            return SimpleNamespace(contents=[SimpleNamespace(text="final-code")])

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

    generated = tool.select_and_execute_template("circuit breaker")
    assert generated == "final-code"

    missing = tool.select_and_execute_template("not_existing")
    assert "No template found" in missing
