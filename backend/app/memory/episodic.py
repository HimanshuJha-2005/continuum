import time
import uuid


class EpisodicMemory:
    """Sessions and turns with timestamps — what happened, and when."""

    def __init__(self, store):
        self.store = store

    def start_session(self, user_id: str, session_id: str, agent_id: str = "scribe") -> str:
        self.store.query(
            user_id,
            """
            MERGE (u:User {id: $user_id})
            MERGE (s:Session {id: $session_id})
            ON CREATE SET s.started_at = timestamp()
            MERGE (u)-[:HAS_SESSION]->(s)
            """,
            {"user_id": user_id, "session_id": session_id},
        )
        return session_id

    def add_turn(self, user_id: str, session_id: str, role: str, content: str) -> str:
        turn_id = str(uuid.uuid4())
        self.store.query(
            user_id,
            """
            MATCH (s:Session {id: $session_id})
            CREATE (t:Turn {id: $turn_id, role: $role, content: $content, ts: timestamp(), seq: $seq})
            CREATE (s)-[:CONTAINS]->(t)
            """,
            {
                "session_id": session_id,
                "turn_id": turn_id,
                "role": role,
                "content": content,
                "seq": time.time_ns(),
            },
        )
        return turn_id

    def recent_sessions(self, user_id: str, limit: int = 5) -> list[dict]:
        result = self.store.ro_query(
            user_id,
            """
            MATCH (u:User {id: $user_id})-[:HAS_SESSION]->(s:Session)
            RETURN s.id, s.started_at
            ORDER BY s.started_at DESC
            LIMIT $limit
            """,
            {"user_id": user_id, "limit": limit},
        )
        return [{"id": r[0], "started_at": r[1]} for r in result.result_set]

    def session_turns(self, user_id: str, session_id: str) -> list[dict]:
        result = self.store.ro_query(
            user_id,
            """
            MATCH (u:User {id: $user_id})-[:HAS_SESSION]->(s:Session {id: $session_id})
                  -[:CONTAINS]->(t:Turn)
            RETURN t.role, t.content, t.ts
            ORDER BY t.ts ASC, t.seq ASC
            """,
            {"user_id": user_id, "session_id": session_id},
        )
        return [{"role": r[0], "content": r[1], "ts": r[2]} for r in result.result_set]
