from functools import lru_cache
import time

from app.config import settings


class LLMError(Exception):
    pass


class LLM:
    def complete(self, prompt: str, system: str = "") -> str:
        raise NotImplementedError


class GeminiLLM(LLM):
    def __init__(self):
        from google import genai
        from google.genai import types

        self.client = genai.Client(
            api_key=settings.gemini_api_key,
            http_options=types.HttpOptions(timeout=30000),
        )
        self.model = settings.gemini_model

    def complete(self, prompt: str, system: str = "") -> str:
        from google.genai import types

        config = types.GenerateContentConfig(
            system_instruction=system or None
        )
        last_error: Exception | None = None
        for attempt in range(2):
            try:
                resp = self.client.models.generate_content(
                    model=self.model, contents=prompt, config=config
                )
                if resp.text:
                    return resp.text
                last_error = LLMError("empty response")
            except Exception as e:
                last_error = e
            time.sleep(1.5)
        raise LLMError(f"gemini failed after retry: {last_error}")


class GroqLLM(LLM):
    def __init__(self):
        from groq import Groq

        self.client = Groq(api_key=settings.groq_api_key)
        self.model = settings.groq_model

    def complete(self, prompt: str, system: str = "") -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        resp = self.client.chat.completions.create(
            model=self.model, messages=messages
        )
        return resp.choices[0].message.content


@lru_cache(maxsize=1)
def get_llm() -> LLM:
    if settings.llm_provider == "groq":
        return GroqLLM()
    return GeminiLLM()
