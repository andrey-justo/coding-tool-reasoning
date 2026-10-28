import os
import tempfile
from threading import Barrier, Lock
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
import yaml

from src.llm_client.multi_model_llm_client import MultiModelLLMClient

_YAML_LOCALAI = [
    {"model_name": "m1", "provider": "LocalAI", "endpoint": "http://localhost:8080"},
    {"model_name": "m2", "provider": "LocalAI", "endpoint": "http://localhost:8081"},
]

_YAML_AZURE = [
    {"model_name": "az", "provider": "AzureOpenAI", "endpoint": "https://azure.com"},
]


def _write_yaml(tmp_dir: str, data: list) -> str:
    path = os.path.join(tmp_dir, "available_models.yaml")
    with open(path, "w") as f:
        yaml.dump(data, f)
    return path


def _make_client(yaml_path: str) -> MultiModelLLMClient:
    with (
        patch(
            "src.llm_client.multi_model_llm_client.os.path.join", return_value=yaml_path
        ),
        patch(
            "src.llm_client.multi_model_llm_client.os.path.exists", return_value=False
        ),
    ):
        return MultiModelLLMClient()


def test_clients_loaded_for_localai_providers():
    with tempfile.TemporaryDirectory() as tmp:
        path = _write_yaml(tmp, _YAML_LOCALAI)
        client = _make_client(path)
    assert "m1" in client.clients
    assert "m2" in client.clients


def test_azure_provider_is_loaded():
    with tempfile.TemporaryDirectory() as tmp:
        path = _write_yaml(tmp, _YAML_AZURE)
        client = _make_client(path)
    assert "az" in client.clients


def test_copilot_provider_alias_uses_sdk_model_without_azure_key():
    with tempfile.TemporaryDirectory() as tmp:
        path = _write_yaml(
            tmp,
            [
                {
                    "model_name": "copilot-codex",
                    "provider": "CopilotSDK",
                    "sdk_model": "gpt-5.3-codex",
                    "timeout": 123,
                }
            ],
        )
        client = _make_client(path)
    sdk_client = client.get_client("copilot-codex")
    assert sdk_client.default_model == "gpt-5.3-codex"
    assert sdk_client.timeout == 123


def test_get_client_returns_correct_client():
    with tempfile.TemporaryDirectory() as tmp:
        path = _write_yaml(tmp, _YAML_LOCALAI)
        client = _make_client(path)
    c = client.get_client("m1")
    assert c is client.clients["m1"]


def test_get_client_raises_for_unknown_model():
    with tempfile.TemporaryDirectory() as tmp:
        path = _write_yaml(tmp, _YAML_LOCALAI)
        client = _make_client(path)
    with pytest.raises(ValueError, match="not supported"):
        client.get_client("unknown")


def test_chat_single_model():
    with tempfile.TemporaryDirectory() as tmp:
        path = _write_yaml(tmp, _YAML_LOCALAI)
        client = _make_client(path)
    client.clients["m1"].chat = MagicMock(return_value="response")
    result = client.chat("hello", model="m1")
    assert result == "response"


def test_chat_multi_model():
    with tempfile.TemporaryDirectory() as tmp:
        path = _write_yaml(tmp, _YAML_LOCALAI)
        client = _make_client(path)
    client.clients["m1"].chat = MagicMock(return_value="r1")
    client.clients["m2"].chat = MagicMock(return_value="r2")
    result = client.chat("hello", model=["m1", "m2"])
    assert result == {"m1": "r1", "m2": "r2"}


def test_openai_client_returns_client():
    with tempfile.TemporaryDirectory() as tmp:
        path = _write_yaml(tmp, _YAML_LOCALAI)
        client = _make_client(path)
    client.default_model = "m1"
    assert client.openai_client() is client.clients["m1"]


@pytest.mark.parametrize("api_key_name", ["AUTH_KEY", "auth_key", "API_KEY"])
def test_process_environment_is_loaded_without_dotenv(monkeypatch, api_key_name):
    for name in ("AUTH_KEY", "auth_key", "API_KEY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv(api_key_name, "test-key")
    monkeypatch.setenv("DEFAULT_MODEL", "m1")
    with tempfile.TemporaryDirectory() as tmp:
        path = _write_yaml(tmp, _YAML_LOCALAI)
        client = _make_client(path)
    assert client.default_model == "m1"
    assert client.api_key == "test-key"
    assert client.get_client() is client.clients["m1"]
    client.clients["m1"].chat = MagicMock(return_value="generated")
    assert client.chat("prompt") == "generated"


def test_dotenv_defaults_do_not_override_inherited_model(monkeypatch):
    monkeypatch.setenv("DEFAULT_MODEL", "m1")
    with tempfile.TemporaryDirectory() as tmp:
        path = _write_yaml(tmp, _YAML_LOCALAI)
        with (
            patch(
                "src.llm_client.multi_model_llm_client.os.path.join", return_value=path
            ),
            patch(
                "src.llm_client.multi_model_llm_client.os.path.exists",
                return_value=True,
            ),
            patch("src.llm_client.multi_model_llm_client.load_dotenv") as load,
        ):
            client = MultiModelLLMClient()
    load.assert_called_once_with(path)
    assert client.get_client() is client.clients["m1"]


def test_batch_is_bounded_and_preserves_input_order():
    with tempfile.TemporaryDirectory() as tmp:
        client = _make_client(_write_yaml(tmp, _YAML_LOCALAI))
    barrier = Barrier(3)
    lock = Lock()
    active = peak = 0

    def generate(prompt, **kwargs):
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
        try:
            barrier.wait(timeout=5)
            return f"response-{prompt}"
        finally:
            with lock:
                active -= 1

    client.default_model = "m1"
    client.clients["m1"] = SimpleNamespace(
        chat=generate, supports_parallel_requests=True
    )
    prompts = [str(index) for index in range(6)]
    assert client.chat_batch(prompts, max_concurrency=3) == [
        f"response-{prompt}" for prompt in prompts
    ]
    assert peak == 3


def test_batch_keeps_unsupported_backends_serial_and_returns_errors(caplog):
    with tempfile.TemporaryDirectory() as tmp:
        client = _make_client(_write_yaml(tmp, _YAML_LOCALAI))
    client.default_model = "m1"
    chat = MagicMock(side_effect=["first", RuntimeError("failed chunk"), "third"])
    client.clients["m1"].chat = chat
    with patch("src.llm_client.multi_model_llm_client.ThreadPoolExecutor") as executor:
        responses = client.chat_batch(["a", "b", "c"], max_concurrency=3)
    executor.assert_not_called()
    assert responses[0] == "first"
    assert isinstance(responses[1], RuntimeError)
    assert responses[2] == "third"
    assert "Batch request 2/3 failed" in caplog.text
    assert "Traceback" in caplog.text


def test_batch_rejects_nonpositive_concurrency():
    with tempfile.TemporaryDirectory() as tmp:
        client = _make_client(_write_yaml(tmp, _YAML_LOCALAI))
    with pytest.raises(ValueError, match="must be positive"):
        client.chat_batch(["prompt"], max_concurrency=0)
