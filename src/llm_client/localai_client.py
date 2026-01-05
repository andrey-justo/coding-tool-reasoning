from agent_framework import ChatClientProtocol
import requests
import json
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from src.errors.TextLLMException import TextLLMException


class LocalAIClient(ChatClientProtocol):
    """
    Simple HTTP client for a LocalAI server.
    Assumes LocalAI chat completions endpoint at {endpoint}/v1/chat/completions
    and returns the first choice's message content.
    """
    def __init__(self, endpoint="http://localhost:8080", default_model=None, api_key=None, timeout=600):
        self.endpoint = endpoint.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.default_model = default_model
        self.session = self._create_session()

    def _create_session(self):
        """Create a requests session with retry logic and connection pooling."""
        session = requests.Session()
        
        # Retry strategy for transient failures
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["POST"]
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session

    def _headers(self):
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self.api_key:
            # send as API token (project code will set API_KEY in .env)
            headers["Authorization"] = f"{self.api_key}"
        return headers

    def chat(self, prompt, model=None, **kwargs):
        # Use chat completions endpoint format
        url = f"{self.endpoint}/v1/chat/completions"
        payload = {
            "model": model or self.default_model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": kwargs.get("max_tokens", 512),
        }
        
        try:
            # Use session with connection pooling for better stability
            # timeout as tuple: (connect_timeout, read_timeout)
            resp = self.session.post(
                url, 
                headers=self._headers(), 
                json=payload, 
                timeout=(10, self.timeout),
                stream=False  # Load full response before processing
            )
            resp.raise_for_status()
            data = resp.json()

            # OpenAI-style chat response
            return data["choices"][0]["message"]["content"]
        except requests.exceptions.Timeout as e:
            raise TextLLMException(f"Request timeout: {e}")
        except requests.exceptions.ConnectionError as e:
            raise TextLLMException(f"Connection error: {e}")
        except requests.exceptions.RequestException as e:
            raise TextLLMException(f"Request failed: {e}")
        except Exception as e:
            raise TextLLMException(f"Unexpected error: {e}")
