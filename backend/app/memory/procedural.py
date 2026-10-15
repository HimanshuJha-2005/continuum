class ProceduralMemory:
    """Preferences and learned procedures — how the agent should behave for this user."""

    def __init__(self, store):
        self.store = store

    def record_preference(self, user_id: str, key: str, value: str):
        raise NotImplementedError

    def record_procedure(self, user_id: str, name: str, steps: list, trigger: str):
        raise NotImplementedError

    def preferences(self, user_id: str):
        raise NotImplementedError

    def procedures(self, user_id: str, trigger: str | None = None):
        raise NotImplementedError
