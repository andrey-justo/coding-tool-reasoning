from agent_framework import ChatClientProtocol
import requests
import json

class LocalAIClient(ChatClientProtocol):
	"""
	Simple HTTP client for a LocalAI server.
	Assumes LocalAI chat completions endpoint at {endpoint}/v1/chat/completions
	and returns the first choice's message content.
	"""
	def __init__(self, endpoint="http://localhost:8080", api_key=None, timeout=30):
		self.endpoint = endpoint.rstrip("/")
		self.api_key = api_key
		self.timeout = timeout

	def _headers(self):
		headers = {"Content-Type": "application/json"}
		if self.api_key:
			# send as Bearer token (project code will set API_KEY in .env)
			headers["Authorization"] = f"Bearer {self.api_key}"
		return headers

	def chat(self, prompt, model=None, **kwargs):
		# Use chat completions endpoint format
		url = f"{self.endpoint}/v1/chat/completions"
		payload = {
			"model": model or "localai",
			"messages": [{"role": "user", "content": prompt}],
			"max_tokens": kwargs.get("max_tokens", 512),
		}
		resp = requests.post(url, headers=self._headers(), json=payload, timeout=self.timeout)
		resp.raise_for_status()
		data = resp.json()
		# Try common Chat-style response shapes
		try:
			# OpenAI-style chat response
			return data["choices"][0]["message"]["content"]
		except Exception:
			# Fallback to text/completion style
			text = data.get("choices", [{}])[0].get("text") or data.get("result", "")
			return text
