import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from copilot.session_events import AssistantMessageData, SessionEvent, SessionEventType

from src.errors.TextLLMException import TextLLMException
from src.llm_client.copilot_sdk_client import CopilotSDKClient
from src.main import main
from src.models.swe_config import ToolExecutionConfig


def _message(content, *, phase="final_answer", agent_id=None):
    return SessionEvent(
        data=AssistantMessageData(
            content=content, message_id=str(uuid4()), phase=phase
        ),
        id=uuid4(),
        timestamp=datetime.now(timezone.utc),
        type=SessionEventType.ASSISTANT_MESSAGE,
        agent_id=agent_id,
    )


@pytest.fixture
def sdk():
    CopilotSDKClient.shutdown()
    with patch("src.llm_client.copilot_sdk_client.CopilotClient") as factory:
        client = factory.return_value.__aenter__.return_value
        session = MagicMock()
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock(return_value=False)
        session.send_and_wait = AsyncMock(return_value=_message("generated"))
        client.create_session = AsyncMock(return_value=session)
        client.list_models = AsyncMock(
            return_value=[SimpleNamespace(id="gpt-5.3-codex", name="GPT-5.3-Codex")]
        )
        try:
            yield factory, client, session
        finally:
            CopilotSDKClient.shutdown()


def test_text_only_session_and_cleanup(sdk):
    factory, client, session = sdk
    assert CopilotSDKClient("gpt-5.3-codex", timeout=12).chat("prompt") == "generated"
    options = client.create_session.call_args.kwargs
    assert options["model"] == "gpt-5.3-codex"
    assert options["available_tools"] == []
    assert options["skip_custom_instructions"] is True
    assert options["enable_config_discovery"] is False
    assert options["enable_file_hooks"] is False
    assert options["enable_skills"] is False
    assert options["enable_host_git_operations"] is False
    assert options["enable_session_store"] is False
    assert options["mcp_servers"] == {}
    assert options["system_message"]["mode"] == "replace"
    assert options["on_permission_request"](None, None).feedback
    session.send_and_wait.assert_awaited_once_with("prompt", timeout=12)
    session.__aexit__.assert_awaited_once()
    factory.return_value.__aexit__.assert_not_awaited()
    CopilotSDKClient.shutdown()
    factory.return_value.__aexit__.assert_awaited_once()


@pytest.mark.asyncio
async def test_sync_chat_inside_existing_event_loop(sdk):
    assert CopilotSDKClient("gpt-5.3-codex").chat("prompt") == "generated"
    assert asyncio.get_running_loop().is_running()


def test_model_override_and_unsupported_controls(sdk, caplog):
    _, client, _ = sdk
    CopilotSDKClient("default").chat(
        "prompt", model="override", temperature=0.2, seed=42
    )
    assert client.create_session.call_args.kwargs["model"] == "override"
    assert "seed, temperature" in caplog.text
    assert "not seed/temperature controlled" in caplog.text


def test_model_discovery(sdk):
    assert CopilotSDKClient.list_models() == [
        {"id": "gpt-5.3-codex", "name": "GPT-5.3-Codex"}
    ]


@pytest.mark.parametrize("content", ["", "   "])
def test_empty_response_is_an_error(sdk, content):
    _, _, session = sdk
    session.send_and_wait.return_value = _message(content)
    with pytest.raises(TextLLMException, match="no textual output after 2 attempts"):
        CopilotSDKClient("gpt-5.3-codex").chat("prompt")
    assert session.__aexit__.await_count == 2


def test_absent_response_is_an_error(sdk):
    _, _, session = sdk
    session.send_and_wait.return_value = None
    with pytest.raises(TextLLMException, match="no textual output"):
        CopilotSDKClient("gpt-5.3-codex").chat("prompt")


def test_empty_response_is_retried_in_fresh_session(sdk, caplog):
    _, client, session = sdk
    session.send_and_wait.side_effect = [None, _message("recovered")]
    assert CopilotSDKClient("gpt-5.3-codex").chat("prompt") == "recovered"
    assert client.create_session.await_count == 2
    assert session.__aexit__.await_count == 2
    assert "retrying in a fresh session" in caplog.text


def test_final_answer_is_not_lost_to_trailing_empty_commentary(sdk):
    _, client, session = sdk

    async def send(prompt, **kwargs):
        observe = client.create_session.call_args.kwargs["on_event"]
        observe(_message("progress", phase="commentary"))
        observe(_message("complete final answer"))
        return _message("", phase="commentary")

    session.send_and_wait.side_effect = send
    assert CopilotSDKClient("gpt-5.3-codex").chat("prompt") == "complete final answer"
    assert client.create_session.await_count == 1


@pytest.mark.parametrize(
    "message",
    [
        _message("progress only", phase="commentary"),
        _message("child answer", agent_id="child"),
    ],
)
def test_commentary_and_subagent_messages_are_not_final_answers(sdk, message):
    _, _, session = sdk
    session.send_and_wait.return_value = message
    with pytest.raises(TextLLMException, match="no textual output after 2 attempts"):
        CopilotSDKClient("gpt-5.3-codex").chat("prompt")


def test_final_event_can_supply_text_when_wait_returns_none(sdk):
    _, client, session = sdk

    async def send(prompt, **kwargs):
        client.create_session.call_args.kwargs["on_event"](_message("final from event"))
        return None

    session.send_and_wait.side_effect = send
    assert CopilotSDKClient("gpt-5.3-codex").chat("prompt") == "final from event"


def test_timeout_is_shared_across_empty_response_retry(sdk):
    _, _, session = sdk

    async def send(prompt, **kwargs):
        if session.send_and_wait.await_count > 1:
            await asyncio.sleep(3600)
        return None

    session.send_and_wait.side_effect = send
    with pytest.raises(TextLLMException, match="timeout after 1.0s"):
        CopilotSDKClient("gpt-5.3-codex", timeout=1.0).chat("prompt")
    assert session.send_and_wait.await_count == 2


@pytest.mark.parametrize(
    "error", [TimeoutError("timeout"), RuntimeError("auth failed")]
)
def test_runtime_errors_surface_and_resources_close(sdk, error):
    factory, _, session = sdk
    session.send_and_wait.side_effect = error
    with pytest.raises(TextLLMException, match="Copilot SDK request failed"):
        CopilotSDKClient("gpt-5.3-codex").chat("prompt")
    session.__aexit__.assert_awaited_once()
    CopilotSDKClient.shutdown()
    factory.return_value.__aexit__.assert_awaited_once()
    assert session.send_and_wait.await_count == 1


@pytest.mark.parametrize(
    ("model", "timeout", "message"),
    [("", 600, "model is required"), ("model", 0, "timeout must be positive")],
)
def test_invalid_configuration(model, timeout, message):
    with pytest.raises(ValueError, match=message):
        CopilotSDKClient(model, timeout=timeout)


def test_cli_model_listing(sdk, monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["main", "copilot-models"])
    main()
    assert capsys.readouterr().out == "gpt-5.3-codex\tGPT-5.3-Codex\n"


def test_runtime_is_shared_across_clients_but_sessions_are_fresh(sdk):
    factory, client, session = sdk
    for model in ("first-model", "second-model", "first-model"):
        assert CopilotSDKClient(model).chat("prompt") == "generated"
    factory.assert_called_once()
    assert client.create_session.await_count == 3
    assert session.__aexit__.await_count == 3
    assert [call.kwargs["model"] for call in client.create_session.await_args_list] == [
        "first-model",
        "second-model",
        "first-model",
    ]


def test_shutdown_is_idempotent_and_next_call_starts_a_new_runtime(sdk):
    factory, _, _ = sdk
    assert CopilotSDKClient("model").chat("first") == "generated"
    CopilotSDKClient.shutdown()
    CopilotSDKClient.shutdown()
    assert CopilotSDKClient("model").chat("second") == "generated"
    assert factory.call_count == 2
    assert factory.return_value.__aexit__.await_count == 1


def test_session_failure_does_not_restart_the_shared_runtime(sdk):
    factory, _, session = sdk
    session.send_and_wait.side_effect = [RuntimeError("failed session"), _message("ok")]
    client = CopilotSDKClient("model")
    with pytest.raises(TextLLMException, match="failed session"):
        client.chat("first")
    assert client.chat("second") == "ok"
    factory.assert_called_once()


def test_concurrent_requests_share_runtime_but_not_sessions(sdk):
    factory, client, _ = sdk
    active = peak = 0
    ready = asyncio.Event()
    sessions = []

    async def create_session(**kwargs):
        session = MagicMock()
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock(return_value=False)

        async def send(prompt, **kwargs):
            nonlocal active, peak
            active += 1
            peak = max(peak, active)
            if active == 3:
                ready.set()
            try:
                await asyncio.wait_for(ready.wait(), timeout=5)
                return _message(prompt)
            finally:
                active -= 1

        session.send_and_wait = AsyncMock(side_effect=send)
        sessions.append(session)
        return session

    client.create_session.side_effect = create_session
    with ThreadPoolExecutor(max_workers=3) as executor:
        responses = list(
            executor.map(CopilotSDKClient("model").chat, ["first", "second", "third"])
        )
    assert responses == ["first", "second", "third"]
    assert peak == 3
    assert len(sessions) == 3
    assert all(session.__aexit__.await_count == 1 for session in sessions)
    factory.assert_called_once()


def test_chunk_concurrency_defaults_to_serial_and_is_bounded():
    assert ToolExecutionConfig().max_generation_concurrency == 1
    assert ToolExecutionConfig(max_generation_concurrency=3).max_generation_concurrency == 3
    for invalid in (0, 9):
        with pytest.raises(ValueError):
            ToolExecutionConfig(max_generation_concurrency=invalid)
