import logging
import os
from concurrent.futures import ThreadPoolExecutor

import yaml
from dotenv import load_dotenv

from src.llm_client.azure_responses_client import AzureResponsesClient
from src.llm_client.copilot_sdk_client import CopilotSDKClient
from src.llm_client.localai_client import LocalAIClient

logger = logging.getLogger(__name__)


class MultiModelLLMClient:
    """
    Wrapper for OpenAIChatClient to support multiple model selection.
    """

    def __init__(self):
        self.default_model = None
        self.api_key = None
        self.load_env()
        self.clients = {}
        # Load model configuration from available_models.yaml
        config_path = os.path.join(
            os.path.dirname(__file__), "../../available_models.yaml"
        )
        with open(config_path, "r", encoding="utf-8") as f:
            models_config = yaml.safe_load(f)
        for model_info in models_config:
            model_name = model_info.get("model_name")
            provider = model_info.get("provider")
            endpoint = model_info.get("endpoint")
            api_version = model_info.get("api_version")

            if provider == "CopilotSDK":
                self.clients[model_name] = CopilotSDKClient(
                    default_model=model_info.get("sdk_model") or model_name,
                    timeout=model_info.get("timeout", 600),
                )
            elif provider in {"AzureOpenAI", "AzureResponses"}:
                self.clients[model_name] = AzureResponsesClient(
                    endpoint=endpoint,
                    default_model=model_name,
                    api_key=self.api_key,
                    api_version=api_version,
                )
            elif provider == "LocalAI":
                # Instantiate the LocalAI HTTP client wrapper
                self.clients[model_name] = LocalAIClient(
                    endpoint=endpoint, default_model=model_name, api_key=self.api_key
                )

    def load_env(self):
        env_path = os.path.join(os.path.dirname(__file__), "../../.env")
        if os.path.exists(env_path):
            load_dotenv(env_path)
        self.api_key = (
            os.getenv("AUTH_KEY") or os.getenv("auth_key") or os.getenv("API_KEY")
        )
        self.default_model = os.getenv("DEFAULT_MODEL")

    def get_client(self, model=None):
        model = model or self.default_model
        if model not in self.clients:
            raise ValueError(f"Model '{model}' is not supported.")
        return self.clients[model]

    def chat(self, prompt, model=None, **kwargs):
        """
        If model is a list, call each and return a dict of model:response.
        If model is a string or None, return the single response.
        """
        if isinstance(model, list):
            results = {}
            for m in model:
                client = self.get_client(m)
                results[m] = client.chat(prompt, **kwargs)
            return results
        else:
            client = self.get_client(model)
            return client.chat(prompt, **kwargs)

    def openai_client(self, model=None):
        if model is None:
            model = self.default_model
        return self.get_client(model)

    def chat_batch(
        self, prompts: list[str], *, max_concurrency: int = 1, **kwargs
    ) -> list[str | Exception]:
        """Return ordered responses or explicit per-request errors."""
        if max_concurrency < 1:
            raise ValueError("max_concurrency must be positive")
        client = self.get_client()
        workers = (
            max_concurrency
            if getattr(client, "supports_parallel_requests", False)
            else 1
        )

        def generate(item: tuple[int, str]) -> str | Exception:
            index, prompt = item
            try:
                return client.chat(prompt, **kwargs)
            except Exception as exc:
                logger.warning(
                    "Batch request %s/%s failed: %s",
                    index + 1,
                    len(prompts),
                    exc,
                    exc_info=True,
                )
                return exc

        if workers == 1 or len(prompts) <= 1:
            return [generate(item) for item in enumerate(prompts)]
        with ThreadPoolExecutor(max_workers=min(workers, len(prompts))) as executor:
            return list(executor.map(generate, enumerate(prompts)))
