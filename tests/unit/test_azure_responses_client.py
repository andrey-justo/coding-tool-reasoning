from __future__ import annotations

import requests
import pytest

from src.errors.TextLLMException import TextLLMException
from src.llm_client.azure_responses_client import AzureResponsesClient


class _FakeResponse:
    def __init__(self, payload: dict | None = None, raise_exc: Exception | None = None):
        self._payload = payload or {}
        self._raise_exc = raise_exc

    def raise_for_status(self) -> None:
        if self._raise_exc:
            raise self._raise_exc

    def json(self) -> dict:
        return self._payload


class _FakeSession:
    def __init__(self, response: _FakeResponse | None = None, exc: Exception | None = None):
        self._response = response or _FakeResponse()
        self._exc = exc
        self.last_post: dict | None = None

    def post(self, *args, **kwargs):
        self.last_post = {"args": args, "kwargs": kwargs}
        if self._exc:
            raise self._exc
        return self._response


class _Unexpected:
    pass


def test_constructor_requires_endpoint() -> None:
    with pytest.raises(ValueError):
        AzureResponsesClient(endpoint="", default_model="gpt")


def test_headers_include_api_key_when_present() -> None:
    client = AzureResponsesClient(endpoint="https://example", default_model="gpt", api_key="k")
    headers = client._headers()
    assert headers["api-key"] == "k"


def test_extract_text_prefers_output_text_then_content_blocks() -> None:
    assert AzureResponsesClient._extract_text({"output_text": "direct"}) == "direct"

    text = AzureResponsesClient._extract_text(
        {
            "output": [
                {"content": [{"text": "line1"}, {"text": "line2"}]},
                {"content": ["bad", {"text": "line3"}]},
            ]
        }
    )
    assert text == "line1\nline2\nline3"


def test_extract_text_raises_when_no_text_available() -> None:
    with pytest.raises(TextLLMException):
        AzureResponsesClient._extract_text({"output": [{"content": [{"foo": "bar"}]}]})


def test_chat_success_builds_payload_and_returns_text() -> None:
    client = AzureResponsesClient(endpoint="https://example", default_model="gpt")
    fake = _FakeSession(response=_FakeResponse({"output_text": "ok"}))
    client.session = fake

    result = client.chat("hello", temperature=0.2)

    assert result == "ok"
    kwargs = fake.last_post["kwargs"]
    assert kwargs["json"]["model"] == "gpt"
    assert kwargs["json"]["temperature"] == 0.2
    assert kwargs["timeout"] == (10, client.timeout)


def test_chat_wraps_timeout_connection_and_request_errors() -> None:
    client = AzureResponsesClient(endpoint="https://example", default_model="gpt")

    client.session = _FakeSession(exc=requests.exceptions.Timeout("t"))
    with pytest.raises(TextLLMException, match="Request timeout"):
        client.chat("hello")

    client.session = _FakeSession(exc=requests.exceptions.ConnectionError("c"))
    with pytest.raises(TextLLMException, match="Connection error"):
        client.chat("hello")

    client.session = _FakeSession(exc=requests.exceptions.RequestException("r"))
    with pytest.raises(TextLLMException, match="Request failed"):
        client.chat("hello")


def test_chat_wraps_unexpected_and_preserves_text_exception() -> None:
    client = AzureResponsesClient(endpoint="https://example", default_model="gpt")

    client.session = _FakeSession(exc=RuntimeError("x"))
    with pytest.raises(TextLLMException, match="Unexpected error"):
        client.chat("hello")

    client.session = _FakeSession(response=_FakeResponse({}))
    with pytest.raises(TextLLMException, match="no textual output"):
        client.chat("hello")
