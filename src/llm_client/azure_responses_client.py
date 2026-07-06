import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from src.errors.TextLLMException import TextLLMException


class AzureResponsesClient:
    """HTTP client for Azure OpenAI Responses API compatible endpoints."""

    def __init__(
        self,
        endpoint: str,
        default_model: str,
        api_key: str | None = None,
        api_version: str | None = None,
        timeout: int = 600,
    ) -> None:
        if not endpoint:
            raise ValueError("Azure responses endpoint is required")
        self.endpoint = endpoint
        self.default_model = default_model
        self.api_key = api_key
        self.api_version = api_version
        self.timeout = timeout
        self.session = self._create_session()

    def _create_session(self) -> requests.Session:
        session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["POST"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session

    def _headers(self) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self.api_key:
            headers["api-key"] = self.api_key
        return headers

    @staticmethod
    def _extract_text(data: dict) -> str:
        output_text = data.get("output_text")
        if isinstance(output_text, str) and output_text.strip():
            return output_text

        output = data.get("output")
        if isinstance(output, list):
            chunks: list[str] = []
            for item in output:
                content = item.get("content") if isinstance(item, dict) else None
                if not isinstance(content, list):
                    continue
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    text = block.get("text")
                    if isinstance(text, str) and text.strip():
                        chunks.append(text)
            if chunks:
                return "\n".join(chunks)

        raise TextLLMException("Azure Responses API returned no textual output")

    def chat(self, prompt: str, model: str | None = None, **kwargs) -> str:
        payload = {
            "model": model or self.default_model,
            "input": [
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": prompt}],
                }
            ],
        }
        if "temperature" in kwargs:
            payload["temperature"] = kwargs["temperature"]

        try:
            resp = self.session.post(
                self.endpoint,
                headers=self._headers(),
                json=payload,
                timeout=(10, self.timeout),
                stream=False,
            )
            resp.raise_for_status()
            return self._extract_text(resp.json())
        except requests.exceptions.Timeout as e:
            raise TextLLMException(f"Request timeout: {e}")
        except requests.exceptions.ConnectionError as e:
            raise TextLLMException(f"Connection error: {e}")
        except requests.exceptions.RequestException as e:
            raise TextLLMException(f"Request failed: {e}")
        except TextLLMException:
            raise
        except Exception as e:
            raise TextLLMException(f"Unexpected error: {e}")
