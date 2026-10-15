class ProceduralMemory:
    """Preferences and learned procedures — how the agent should behave for this user."""

    def __init__(self, store):
        self.store = store

    def record_preference(self, user_id: str, key: str, value: str) -> None:
        self.store.query(
            user_id,
            """
            MERGE (u:User {id: $user_id})
            MERGE (p:Preference {key: $key})
            SET p.value = $value, p.updated_at = timestamp()
            MERGE (u)-[:PREFERS]->(p)
            """,
            {"user_id": user_id, "key": key, "value": value},
        )

    def record_procedure(
        self, user_id: str, name: str, steps: list, trigger: str
    ) -> None:
        self.store.query(
            user_id,
            """
            MERGE (u:User {id: $user_id})
            MERGE (p:Procedure {name: $name})
            SET p.steps = $steps, p.trigger = $trigger, p.updated_at = timestamp()
            MERGE (u)-[:HAS_PROCEDURE]->(p)
            """,
            {"user_id": user_id, "name": name, "steps": steps, "trigger": trigger},
        )

    def preferences(self, user_id: str) -> dict:
        result = self.store.ro_query(
            user_id,
            """
            MATCH (u:User {id: $user_id})-[:PREFERS]->(p:Preference)
            RETURN p.key, p.value
            """,
            {"user_id": user_id},
        )
        return {r[0]: r[1] for r in result.result_set}

    def procedures(self, user_id: str, trigger: str | None = None) -> list[dict]:
        result = self.store.ro_query(
            user_id,
            """
            MATCH (u:User {id: $user_id})-[:HAS_PROCEDURE]->(p:Procedure)
            WHERE $trigger IS NULL OR p.trigger = $trigger
            RETURN p.name, p.steps, p.trigger
            """,
            {"user_id": user_id, "trigger": trigger},
        )
        return [{"name": r[0], "steps": r[1], "trigger": r[2]} for r in result.result_set]
