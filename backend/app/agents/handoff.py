HANDOFF_QUERY = """
CREATE (from:Agent {id: $from_id})-[:HANDOFF_TO {summary: $summary, ts: timestamp()}]->(to:Agent {id: $to_id})
"""


class Handoff:
    def __init__(self, store):
        self.store = store

    def create(self, user_id: str, from_id: str, to_id: str, summary: str):
        raise NotImplementedError

    def latest_for(self, user_id: str, agent_id: str):
        raise NotImplementedError

    def shared_state(self, user_id: str, key: str):
        raise NotImplementedError

    def set_shared_state(self, user_id: str, key: str, value: str, agent_id: str):
        raise NotImplementedError
