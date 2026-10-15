from app.config import settings


class LLMError(Exception):
    pass


class LLM:
    def complete(self, prompt: str, system: str = "") -> str:
        raise NotImplementedError


class GeminiLLM(LLM):
    def __init__(self):
        import google.generativeai as genai

        genai.configure(api_key=settings.gemini_api_key)
        self.model = genai.GenerativeModel(settings.gemini_model)

    def complete(self, prompt: str, system: str = "") -> str:
        text = f"{system}\n\n{prompt}" if system else prompt
        resp = self.model.generate_content(text)
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


def get_llm() -> LLM:
    if settings.llm_provider == "groq":
        return GroqLLM()
    return GeminiLLM()
