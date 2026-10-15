class SemanticMemory:
    """Facts and entities extracted from conversation, linked in the graph."""

    def __init__(self, store, llm=None):
        self.store = store
        self.llm = llm

    def extract(self, user_id: str, text: str):
        raise NotImplementedError

    def upsert_fact(self, user_id: str, fact: dict):
        raise NotImplementedError

    def recall(self, user_id: str, query: str, limit: int = 10):
        raise NotImplementedError

    def supersede(self, user_id: str, old_fact_id: str, new_fact: dict):
        raise NotImplementedError
