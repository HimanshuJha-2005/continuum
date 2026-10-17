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
        self.models = tuple(
            dict.fromkeys(
                [settings.gemini_model, "gemini-3.6-flash", "gemini-3.8-flash"]
            )
        )

    def complete(self, prompt: str, system: str = "") -> str:
        from google.genai import types

        config = types.GenerateContentConfig(
            system_instruction=system or None
        )
        errors: list[str] = []
        for model in self.models:
            last = ""
            for attempt in range(2):
                try:
                    resp = self.client.models.generate_content(
                        model=model, contents=prompt, config=config
                    )
                    if resp.text:
                        return resp.text
                    last = "empty response"
                except Exception as e:
                    last = str(e)
                if "RESOURCE_EXHAUSTED" in last:
                    break
                time.sleep(1.5)
            errors.append(f"{model}: {last[:160]}")
        raise LLMError(f"all gemini models failed: {' | '.join(errors)}")


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
