from app.agents.base import Agent


class Scout(Agent):
    def __init__(self, store, llm):
        super().__init__("scout", "Scout", "researcher", store, llm)
