"""
Handles calls to LLM models (e.g., OpenAI API).
"""
import openai

class LLMCaller:
    def __init__(self, api_key):
        self.api_key = api_key
        openai.api_key = api_key

    def call(self, prompt, model="gpt-3.5-turbo"):
        response = openai.ChatCompletion.create(
            model=model,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message["content"]