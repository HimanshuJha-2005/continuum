from functools import lru_cache

from app.config import settings


class LLMError(Exception):
    pass


class LLM:
    def complete(self, prompt: str, system: str = "") -> str:
        raise NotImplementedError


class GeminiLLM(LLM):
    def __init__(self):
        from google import genai

        self.client = genai.Client(api_key=settings.gemini_api_key)
        self.model = settings.gemini_model

    def complete(self, prompt: str, system: str = "") -> str:
        from google.genai import types

        config = types.GenerateContentConfig(
            system_instruction=system or None
        )
        resp = self.client.models.generate_content(
            model=self.model, contents=prompt, config=config
        )
        return resp.text


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
