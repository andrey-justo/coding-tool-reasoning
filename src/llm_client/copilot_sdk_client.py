"""Text-only Copilot SDK adapter for the synchronous experiment pipeline."""

from __future__ import annotations

import asyncio
import atexit
import logging
import time
from contextlib import AsyncExitStack
from tempfile import TemporaryDirectory
from threading import Lock, Thread
from typing import Callable, Coroutine, TypeVar
from uuid import uuid4

from copilot import CopilotClient
from copilot.generated.rpc import PermissionDecisionReject
from copilot.session_events import AssistantMessageData, SessionEvent

from src.errors.TextLLMException import TextLLMException

logger = logging.getLogger(__name__)
_T = TypeVar("_T")


class _SharedCopilotRuntime:
    def __init__(self) -> None:
        self._loop = asyncio.new_event_loop()
        self._thread = Thread(
            target=self._serve, name="copilot-sdk-runtime", daemon=True
        )
        self._resources = AsyncExitStack()
        self._initialization_lock = asyncio.Lock()
        self._client: CopilotClient | None = None
        self._working_directory: str | None = None
        self._thread.start()

    def _serve(self) -> None:
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_forever()
        finally:
            pending = asyncio.all_tasks(self._loop)
            for task in pending:
                task.cancel()
            if pending:
                self._loop.run_until_complete(
                    asyncio.gather(*pending, return_exceptions=True)
                )
            self._loop.run_until_complete(self._loop.shutdown_asyncgens())
            self._loop.close()

    async def _execute(
        self,
        operation: Callable[[CopilotClient, str], Coroutine[None, None, _T]],
        timeout: float,
    ) -> _T:
        async with asyncio.timeout(timeout):
            async with self._initialization_lock:
                if self._client is None:
                    async with AsyncExitStack() as resources:
                        directory = resources.enter_context(
                            TemporaryDirectory(prefix="copilot-text-")
                        )
                        client = await resources.enter_async_context(
                            CopilotClient(working_directory=directory)
                        )
                        self._resources = resources.pop_all()
                        self._client = client
                        self._working_directory = directory
                client = self._client
                directory = self._working_directory
            if client is None or directory is None:
                raise RuntimeError("Copilot runtime did not initialize")
            return await operation(client, directory)

    def run(
        self,
        operation: Callable[[CopilotClient, str], Coroutine[None, None, _T]],
        timeout: float,
    ) -> _T:
        return asyncio.run_coroutine_threadsafe(
            self._execute(operation, timeout), self._loop
        ).result()

    def close(self) -> None:
        try:
            asyncio.run_coroutine_threadsafe(
                self._resources.aclose(), self._loop
            ).result(timeout=30)
        finally:
            self._loop.call_soon_threadsafe(self._loop.stop)
            self._thread.join(timeout=30)
            if self._thread.is_alive():
                raise RuntimeError("Copilot runtime thread did not stop")


_runtime: _SharedCopilotRuntime | None = None
_runtime_lock = Lock()


def _get_runtime() -> _SharedCopilotRuntime:
    global _runtime
    with _runtime_lock:
        if _runtime is None:
            _runtime = _SharedCopilotRuntime()
        return _runtime


class CopilotSDKClient:
    """Use the Copilot runtime's authenticated account, without an Azure key."""

    supports_parallel_requests = True

    def __init__(self, default_model: str, timeout: float = 600) -> None:
        if not default_model:
            raise ValueError("Copilot SDK model is required")
        if timeout <= 0:
            raise ValueError("Copilot SDK timeout must be positive")
        self.default_model = default_model
        self.timeout = timeout

    @staticmethod
    def list_models() -> list[dict[str, str]]:
        async def discover(
            client: CopilotClient, directory: str
        ) -> list[dict[str, str]]:
            models = await client.list_models()
            return [{"id": model.id, "name": model.name} for model in models]

        return _get_runtime().run(discover, timeout=600)

    @staticmethod
    def shutdown() -> None:
        global _runtime
        with _runtime_lock:
            if _runtime is not None:
                runtime, _runtime = _runtime, None
                runtime.close()

    def chat(self, prompt: str, model: str | None = None, **kwargs) -> str:
        if kwargs:
            logger.warning(
                "Copilot SDK does not apply these generation controls: %s. "
                "This response is not seed/temperature controlled.",
                ", ".join(sorted(kwargs)),
            )
        request_id = uuid4().hex[:8]
        selected_model = model or self.default_model
        started = time.monotonic()
        logger.info(
            "Copilot request %s started (model=%s, prompt_chars=%s)",
            request_id,
            selected_model,
            len(prompt),
        )
        try:
            response = _get_runtime().run(
                lambda client, directory: self._chat(
                    prompt, selected_model, client, directory
                ),
                timeout=self.timeout,
            )
            logger.info(
                "Copilot request %s completed in %.2fs (response_chars=%s)",
                request_id,
                time.monotonic() - started,
                len(response),
            )
            return response
        except TimeoutError as exc:
            raise TextLLMException(
                f"Copilot SDK request failed: timeout after {self.timeout}s"
            ) from exc
        except (OSError, RuntimeError, ValueError) as exc:
            raise TextLLMException(f"Copilot SDK request failed: {exc}") from exc

    async def _chat(
        self, prompt: str, model: str, client: CopilotClient, working_directory: str
    ) -> str:
        for attempt in range(1, 3):
            final_text: str | None = None
            phases: set[str] = set()

            def observe(event: SessionEvent) -> None:
                nonlocal final_text
                if event.agent_id or not isinstance(event.data, AssistantMessageData):
                    return
                data = event.data
                phases.add(data.phase or "unspecified")
                if (
                    data.phase in (None, "final_answer")
                    and not data.tool_requests
                    and data.content.strip()
                ):
                    final_text = data.content

            async with await client.create_session(
                model=model,
                available_tools=[],
                on_permission_request=lambda request, context: (
                    PermissionDecisionReject(
                        feedback="This provider only generates text; tools are disabled."
                    )
                ),
                system_message={
                    "mode": "replace",
                    "content": (
                        "You are a text-generation assistant, not an autonomous "
                        "coding agent. All inputs are provided in the user prompt. "
                        "Return the complete requested response in your final answer. "
                        "Do not use tools, announce plans, or send progress updates. "
                        "Follow the requested output format exactly. If code needs "
                        "no changes, return the code rather than an empty response."
                    ),
                },
                on_event=observe,
                working_directory=working_directory,
                skip_custom_instructions=True,
                enable_config_discovery=False,
                enable_file_hooks=False,
                enable_skills=False,
                enable_host_git_operations=False,
                enable_session_store=False,
                mcp_servers={},
            ) as session:
                response = await session.send_and_wait(prompt, timeout=self.timeout)
                if response is not None:
                    observe(response)
                if final_text is not None:
                    return final_text

            details = f"model={model}, phases={','.join(sorted(phases)) or 'none'}"
            if attempt == 1:
                logger.warning(
                    "Copilot SDK returned no final text (%s, attempt=1/2); "
                    "retrying in a fresh session within the request timeout.",
                    details,
                )
            else:
                raise TextLLMException(
                    "Copilot SDK returned no textual output after 2 attempts "
                    f"({details})"
                )


atexit.register(CopilotSDKClient.shutdown)
