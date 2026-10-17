import re

from app.llm import get_llm

RECENT_TURNS = """
MATCH (u:User {id: $user_id})-[:HAS_SESSION]->(:Session)-[:CONTAINS]->(t:Turn)
RETURN t
ORDER BY t.ts DESC, id(t) DESC
LIMIT $limit
"""

FACT_MATCH = """
MATCH (f:Fact)
WHERE any(w IN $words WHERE toLower(f.subject) CONTAINS w
          OR toLower(f.predicate) CONTAINS w
          OR toLower(f.value) CONTAINS w)
AND f.valid_to IS NULL
RETURN f
ORDER BY f.confidence DESC
LIMIT $limit
"""

RECENT_FACTS = """
MATCH (f:Fact)
WHERE f.valid_to IS NULL
RETURN f
ORDER BY f.last_seen DESC, f.confidence DESC
LIMIT $limit
"""

PREFERENCES = """
MATCH (u:User {id: $user_id})-[:PREFERS]->(p:Preference)
RETURN p
"""

SYSTEM_TEMPLATE = """You are {name}, a persistent-memory assistant inside Continuum.
You answer ONLY from the memory context provided: recent conversation turns,
facts, and preferences pulled from your graph memory. The context already
includes facts captured from the current message.
If a fact or preference in the context answers the question, state it directly
and confidently, citing it as [fact: subject predicate value].
If the message states an update (e.g. "we now prefer X"), confirm what the
memory currently holds about it, citing the matching fact.
Only when nothing in the context relates to the question, say the memory does
not contain it yet. Keep answers short and direct."""


class Agent:
    def __init__(self, agent_id: str, name: str, role: str, store, llm=None):
        self.agent_id = agent_id
        self.name = name
        self.role = role
        self.store = store
        self.llm = llm or get_llm()

    def build_context(self, user_id: str, query: str, trace=None) -> dict:
        words = [w.lower() for w in re.findall(r"[A-Za-z0-9+#.]{4,}", query)][:6] or [""]

        result = self.store.ro_query(
            user_id, RECENT_TURNS, {"user_id": user_id, "limit": 8}
        )
        if trace:
            trace.add(RECENT_TURNS, {"user_id": user_id, "limit": 8}, result, "episodic")
        turns = []
        for row in result.result_set:
            node = row[0]
            props = dict(node.properties)
            props["node_id"] = node.id
            turns.append(props)

        result = self.store.ro_query(user_id, FACT_MATCH, {"words": words, "limit": 8})
        if trace:
            trace.add(FACT_MATCH, {"words": words, "limit": 8}, result, "semantic")
        facts: list[dict] = []
        seen: set[int] = set()

        def collect(res) -> None:
            for row in res.result_set:
                node = row[0]
                if node.id in seen:
                    continue
                seen.add(node.id)
                props = dict(node.properties)
                props["node_id"] = node.id
                facts.append(props)

        collect(result)
        if len(facts) < 3:
            fallback = self.store.ro_query(
                user_id, RECENT_FACTS, {"limit": 8 - len(facts)}
            )
            if trace:
                trace.add(RECENT_FACTS, {"limit": 8 - len(facts)}, fallback, "semantic")
            collect(fallback)

        result = self.store.ro_query(user_id, PREFERENCES, {"user_id": user_id})
        if trace:
            trace.add(PREFERENCES, {"user_id": user_id}, result, "procedural")
        preferences = {}
        for row in result.result_set:
            props = dict(row[0].properties)
            preferences[props.get("key", "")] = props.get("value", "")

        return {"turns": turns, "facts": facts, "preferences": preferences}

    def think(
        self, user_id: str, query: str, trace=None, extra_context: str = ""
    ) -> str:
        ctx = self.build_context(user_id, query, trace)
        lines = ["Memory context:"]
        if extra_context:
            lines.append(extra_context)
        if ctx["preferences"]:
            lines.append("Preferences: " + "; ".join(f"{k}={v}" for k, v in ctx["preferences"].items()))
        if ctx["facts"]:
            for f in ctx["facts"]:
                lines.append(f"Fact: {f.get('subject')} {f.get('predicate')} {f.get('value')}")
        for t in reversed(ctx["turns"]):
            lines.append(f"Turn ({t['role']}): {t['content']}")
        lines.append("")
        lines.append(f"Question: {query}")
        return self.llm.complete("\n".join(lines), system=SYSTEM_TEMPLATE.format(name=self.name))
