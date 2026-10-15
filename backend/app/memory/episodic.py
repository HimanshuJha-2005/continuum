class EpisodicMemory:
    """Sessions and turns with timestamps — what happened, and when."""

    def __init__(self, store):
        self.store = store

    def start_session(self, user_id: str, session_id: str, agent_id: str = "scribe"):
        raise NotImplementedError

    def add_turn(self, user_id: str, session_id: str, role: str, content: str):
        raise NotImplementedError

    def recent_sessions(self, user_id: str, limit: int = 5):
        raise NotImplementedError

    def session_turns(self, user_id: str, session_id: str):
        raise NotImplementedError
