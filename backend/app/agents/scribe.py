from app.agents.base import Agent


class Scribe(Agent):
    def __init__(self, store, llm):
        super().__init__("scribe", "Scribe", "summarizer", store, llm)
