import os
import tempfile
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
        patch("src.llm_client.multi_model_llm_client.os.path.join", return_value=yaml_path),
        patch("src.llm_client.multi_model_llm_client.os.path.exists", return_value=False),
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
