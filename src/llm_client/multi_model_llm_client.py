from agent_framework.azure import AzureOpenAIAssistantsClient
from azure.identity import AzureCliCredential
from .localai_client import LocalAIClient
import yaml
import os
from dotenv import load_dotenv


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
            if provider == "AzureOpenAI":
                # Use api_key if available, otherwise fallback to AzureCliCredential
                if self.api_key:
                    self.clients[model_name] = AzureOpenAIAssistantsClient(
                        deployment_name=model_name,
                        endpoint=endpoint,
                        api_key=self.api_key,
                        api_version=api_version,
                    )
                else:
                    self.clients[model_name] = AzureOpenAIAssistantsClient(
                        deployment_name=model_name,
                        endpoint=endpoint,
                        credential=AzureCliCredential(),
                        api_version=api_version,
                    )
            elif provider == "LocalAI":
                # Instantiate the LocalAI HTTP client wrapper
                self.clients[model_name] = LocalAIClient(
                    endpoint=endpoint, default_model=model_name, api_key=self.api_key
                )

    def load_env(self):
        env_path = os.path.join(os.path.dirname(__file__), "../../.env")
        if not os.path.exists(env_path):
            return

        load_dotenv(env_path)
        self.api_key = os.getenv("API_KEY")
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
