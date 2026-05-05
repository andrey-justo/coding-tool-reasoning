from unittest.mock import MagicMock, patch

import pytest
import requests

from src.errors.TextLLMException import TextLLMException
from src.llm_client.localai_client import LocalAIClient


@pytest.fixture()
def client():
    return LocalAIClient(
        endpoint="http://localhost:8080",
        default_model="test-model",
        api_key="secret",
        timeout=30,
    )


def _mock_response(content: str) -> MagicMock:
    resp = MagicMock()
    resp.json.return_value = {
        "choices": [{"message": {"content": content}}]
    }
    resp.raise_for_status.return_value = None
    return resp


def test_headers_include_auth_when_api_key_set(client):
    headers = client._headers()
    assert headers["Authorization"] == "secret"
    assert headers["Content-Type"] == "application/json"


def test_headers_no_auth_when_no_api_key():
    c = LocalAIClient()
    headers = c._headers()
    assert "Authorization" not in headers


def test_chat_returns_content(client):
    with patch.object(client.session, "post", return_value=_mock_response("hello")) as mock_post:
        result = client.chat("Say hello", model="m1")
    assert result == "hello"
    mock_post.assert_called_once()


def test_chat_uses_default_model_when_model_none(client):
    with patch.object(client.session, "post", return_value=_mock_response("ok")) as mock_post:
        client.chat("prompt")
    payload = mock_post.call_args.kwargs["json"]
    assert payload["model"] == "test-model"


def test_chat_raises_text_llm_exception_on_timeout(client):
    with patch.object(client.session, "post", side_effect=requests.exceptions.Timeout("t")):
        with pytest.raises(TextLLMException, match="timeout"):
            client.chat("prompt")


def test_chat_raises_text_llm_exception_on_connection_error(client):
    with patch.object(client.session, "post", side_effect=requests.exceptions.ConnectionError("c")):
        with pytest.raises(TextLLMException, match="Connection error"):
            client.chat("prompt")


def test_chat_raises_text_llm_exception_on_request_exception(client):
    with patch.object(client.session, "post", side_effect=requests.exceptions.RequestException("r")):
        with pytest.raises(TextLLMException, match="Request failed"):
            client.chat("prompt")


def test_chat_raises_text_llm_exception_on_unexpected_error(client):
    with patch.object(client.session, "post", side_effect=KeyError("bad")):
        with pytest.raises(TextLLMException, match="Unexpected error"):
            client.chat("prompt")


def test_create_session_mounts_adapters(client):
    session = client.session
    # Both http:// and https:// should have adapters mounted
    assert "http://" in session.adapters
    assert "https://" in session.adapters
