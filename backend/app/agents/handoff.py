import uuid

HANDOFF_QUERY = """
MERGE (a:Agent {id: $from_id})
MERGE (b:Agent {id: $to_id})
CREATE (a)-[:HANDOFF_TO {
    id: $handoff_id,
    summary: $summary,
    status: 'pending',
    ts: timestamp()
}]->(b)
"""

LATEST_HANDOFF_QUERY = """
MATCH (src:Agent)-[h:HANDOFF_TO]->(dst:Agent {id: $agent_id})
WHERE h.status = 'pending'
RETURN src.id, h.summary, h.ts, h.id
ORDER BY h.ts DESC
LIMIT 1
"""

MARK_CONSUMED = """
MATCH ()-[h:HANDOFF_TO {id: $handoff_id}]->()
SET h.status = 'consumed', h.consumed_at = timestamp()
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

    def entries(self, user_id: str) -> dict:
        result = self.store.ro_query(
            user_id,
            """
            MATCH (s:SharedState {user_id: $user_id})
            RETURN s.key, s.value, s.updated_at
            """,
            {"user_id": user_id},
        )
        return {r[0]: {"value": r[1], "updated_at": r[2]} for r in result.result_set}

    def recent_all(self, user_id: str, limit: int = 20) -> list[dict]:
        result = self.store.ro_query(
            user_id,
            """
            MATCH (a:Agent)-[h:HANDOFF_TO]->(b:Agent)
            RETURN a.id, b.id, h.summary, h.ts, h.status
            ORDER BY h.ts DESC
            LIMIT $limit
            """,
            {"limit": limit},
        )
        return [
            {"from": r[0], "to": r[1], "summary": r[2], "ts": r[3], "status": r[4]}
            for r in result.result_set
        ]

    def latest_for(self, user_id: str, agent_id: str) -> dict | None:
        """Newest pending handoff for this agent (consumed ones never re-inject)."""
        result = self.store.ro_query(
            user_id, LATEST_HANDOFF_QUERY, {"agent_id": agent_id}
        )
        if not result.result_set:
            return None
        row = result.result_set[0]
        return {"from": row[0], "summary": row[1], "ts": row[2], "id": row[3]}

    def mark_consumed(self, user_id: str, handoff_id: str) -> None:
        self.store.query(user_id, MARK_CONSUMED, {"handoff_id": handoff_id})

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
