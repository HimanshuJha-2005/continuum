import uuid

HANDOFF_QUERY = """
MERGE (a:Agent {id: $from_id})
MERGE (b:Agent {id: $to_id})
CREATE (a)-[:HANDOFF_TO {
    id: $handoff_id,
    summary: $summary,
    ts: timestamp()
}]->(b)
"""

LATEST_HANDOFF_QUERY = """
MATCH (src:Agent)-[h:HANDOFF_TO]->(dst:Agent {id: $agent_id})
RETURN src.id, h.summary, h.ts, h.id
ORDER BY h.ts DESC
LIMIT 1
"""

STATE_GET = """
MATCH (s:SharedState {user_id: $user_id, key: $key})
RETURN s.value
"""

STATE_SET = """
MERGE (s:SharedState {user_id: $user_id, key: $key})
SET s.value = $value, s.updated_at = timestamp()
WITH s
MERGE (a:Agent {id: $agent_id})
MERGE (a)-[w:WROTE]->(s)
SET w.ts = timestamp()
"""

STATE_READ = """
MATCH (s:SharedState {user_id: $user_id, key: $key})
WITH s
MERGE (a:Agent {id: $agent_id})
MERGE (a)-[r:READ]->(s)
SET r.ts = timestamp()
"""


class Handoff:
    """Cross-agent handoff + shared key-value state, both audit-edged in the graph."""

    def __init__(self, store):
        self.store = store

    def create(self, user_id: str, from_id: str, to_id: str, summary: str) -> str:
        handoff_id = str(uuid.uuid4())
        self.store.query(
            user_id,
            HANDOFF_QUERY,
            {
                "from_id": from_id,
                "to_id": to_id,
                "summary": summary,
                "handoff_id": handoff_id,
            },
        )
        return handoff_id

    def latest_for(self, user_id: str, agent_id: str) -> dict | None:
        result = self.store.ro_query(
            user_id, LATEST_HANDOFF_QUERY, {"agent_id": agent_id}
        )
        if not result.result_set:
            return None
        row = result.result_set[0]
        return {"from": row[0], "summary": row[1], "ts": row[2], "id": row[3]}

    def shared_state(self, user_id: str, key: str, agent_id: str | None = None):
        if agent_id:
            self.store.query(
                user_id, STATE_READ, {"user_id": user_id, "key": key, "agent_id": agent_id}
            )
        result = self.store.ro_query(user_id, STATE_GET, {"user_id": user_id, "key": key})
        if not result.result_set:
            return None
        return result.result_set[0][0]

    def set_shared_state(
        self, user_id: str, key: str, value: str, agent_id: str
    ) -> None:
        self.store.query(
            user_id,
            STATE_SET,
            {"user_id": user_id, "key": key, "value": value, "agent_id": agent_id},
        )
