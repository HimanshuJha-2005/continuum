import re

from app.llm import get_llm

RECENT_TURNS = """
MATCH (u:User {id: $user_id})-[:HAS_SESSION]->(:Session)-[:CONTAINS]->(t:Turn)
RETURN t
ORDER BY t.ts DESC, t.seq DESC
LIMIT $limit
"""

STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "if", "then", "else", "when",
    "where", "what", "which", "who", "whom", "whose", "how", "why", "is",
    "are", "was", "were", "be", "been", "being", "do", "does", "did",
    "doing", "can", "could", "will", "would", "shall", "should", "may",
    "might", "must", "have", "has", "had", "having", "i", "me", "my",
    "we", "our", "ours", "you", "your", "he", "she", "it", "its", "they",
    "them", "their", "this", "that", "these", "those", "there", "here",
    "of", "to", "in", "on", "at", "by", "for", "with", "about", "as",
    "from", "up", "out", "off", "over", "under", "again", "please", "tell",
}


def significant_words(text: str, limit: int = 6) -> list[str]:
    """Meaningful tokens for retrieval and relevance: 2+ chars, not stopwords,
    deduped in order. Keeps short tech names (Go, API, AWS)."""
    words: list[str] = []
    for w in re.findall(r"[A-Za-z0-9+#.]{2,}", text.lower()):
        w = w.strip(".+#")
        if not w or w in STOPWORDS or w in words:
            continue
        words.append(w)
        if len(words) >= limit:
            break
    return words


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

FULLTEXT_FACTS = """
CALL db.idx.fulltext.queryNodes('Fact', $q) YIELD node, score
WHERE node.valid_to IS NULL
RETURN node, score
ORDER BY score DESC
LIMIT $limit
"""

RECENT_FACTS = """
MATCH (f:Fact)
WHERE f.valid_to IS NULL
RETURN f
ORDER BY f.last_seen DESC, f.confidence DESC
LIMIT $limit
"""

HISTORY = """
MATCH (f:Fact)
WHERE any(w IN $words WHERE toLower(f.subject) CONTAINS w
          OR toLower(f.predicate) CONTAINS w
          OR toLower(f.value) CONTAINS w)
OPTIONAL MATCH (newer:Fact)-[:SUPERSEDES*1..5]->(f)
WITH DISTINCT COALESCE(newer, f) AS root
OPTIONAL MATCH path = (root)-[:SUPERSEDES*1..5]->(old:Fact)
RETURN root, [n IN nodes(path) | n.value] AS evolution
LIMIT 6
"""

HISTORY_CHAINS = """
MATCH path = (root:Fact)-[:SUPERSEDES*1..5]->(old:Fact)
WHERE NOT (root)<-[:SUPERSEDES]-()
RETURN root, [n IN nodes(path) | n.value] AS evolution
ORDER BY root.last_seen DESC
LIMIT 6
"""

TEMPORAL_RE = re.compile(
    r"\b(before|previously|earlier|originally|first|used to|prior|once|"
    r"initially|back then|used-to|was|were|history|before this)\b",
    re.I,
)

ENTITY_CONTEXT = """
MATCH (u:User {id: $user_id})-[:HAS_SESSION]->(:Session)-[:CONTAINS]->(t:Turn)
MATCH (t)-[:MENTIONS]->(e:Entity)
MATCH (e)-[:RELATES]->(f:Fact)
WHERE f.valid_to IS NULL
RETURN DISTINCT f
ORDER BY f.confidence DESC
LIMIT $limit
"""

PREFERENCES = """
MATCH (u:User {id: $user_id})-[:PREFERS]->(p:Preference)
RETURN p
"""

PROCEDURES = """
MATCH (u:User {id: $user_id})-[:HAS_PROCEDURE]->(p:Procedure)
RETURN p
"""

SYSTEM_TEMPLATE = """You are {name}, a persistent-memory assistant inside Continuum.
You answer ONLY from the memory context provided: recent conversation turns,
facts, preferences, and supersession history pulled from your graph memory.
The context already includes facts captured from the current message.
If a fact or preference in the context answers the question, state it directly
and confidently, citing it as [fact: subject predicate value].
If the message states an update or a new preference/fact, confirm what was
recorded directly and naturally: e.g. "Got it — noted that you prefer TypeScript for new frontend projects [fact: TypeScript preferred for new frontend projects]."
Do NOT recite past history or superseded values unless the user explicitly asks
about the past, earlier choices, or how things changed.
If History lines are present and the user asks what something was before,
earlier, originally, or how/when it changed, answer from the history chain
(oldest to newest), quoting each value from the History lines verbatim — never
infer the previous value from the wording of the question or recent turns, e.g.
"Previously <old value from History>, changed to <new value> [fact: ...]".
Only when nothing in the context relates to the question, say the memory does
not contain it yet. If Procedures lines are present and the user asks how to
do something, triggers a recorded procedure, or says they finished a step
(e.g. "done with step 1, what's next?"), use the recorded steps and recent
turns to identify progress and recite or follow the remaining steps in order.
Keep answers short and direct."""


class Agent:
    def __init__(self, agent_id: str, name: str, role: str, store, llm=None):
        self.agent_id = agent_id
        self.name = name
        self.role = role
        self.store = store
        self.llm = llm or get_llm()

    def build_context(self, user_id: str, query: str, trace=None) -> dict:
        words = significant_words(query)

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

        matched = 0
        if words:
            try:
                fulltext = self.store.ro_query(
                    user_id,
                    FULLTEXT_FACTS,
                    {"q": " | ".join(words), "limit": 8},
                )
                if trace:
                    trace.add(
                        FULLTEXT_FACTS,
                        {"q": " | ".join(words), "limit": 8},
                        fulltext,
                        "semantic",
                    )
                collect(fulltext)
            except Exception:
                pass
            if len(facts) < 3:
                result = self.store.ro_query(
                    user_id, FACT_MATCH, {"words": words, "limit": 8 - len(facts)}
                )
                if trace:
                    trace.add(FACT_MATCH, {"words": words, "limit": 8 - len(facts)}, result, "semantic")
                collect(result)
        matched = len(facts)

        history: list[dict] = []
        if words and TEMPORAL_RE.search(query):
            hres = self.store.ro_query(user_id, HISTORY_CHAINS, {})
            if trace:
                trace.add(HISTORY_CHAINS, {}, hres, "temporal")
            for row in hres.result_set:
                root, evolution = row[0], row[1]
                if not evolution or len(evolution) < 2:
                    continue
                props = dict(root.properties) if root else {}
                history.append({"root": props, "evolution": evolution})

        if len(facts) < 3:
            fallback = self.store.ro_query(
                user_id, RECENT_FACTS, {"limit": 8 - len(facts)}
            )
            if trace:
                trace.add(RECENT_FACTS, {"limit": 8 - len(facts)}, fallback, "semantic")
            collect(fallback)

        entities: list[dict] = []
        if words:
            eres = self.store.ro_query(
                user_id, ENTITY_CONTEXT, {"user_id": user_id, "limit": 6}
            )
            if trace:
                trace.add(
                    ENTITY_CONTEXT,
                    {"user_id": user_id, "limit": 6},
                    eres,
                    "semantic",
                )
            for row in eres.result_set:
                node = row[0]
                if node.id in seen:
                    continue
                seen.add(node.id)
                props = dict(node.properties)
                props["node_id"] = node.id
                entities.append(props)
            facts.extend(entities)

        result = self.store.ro_query(user_id, PREFERENCES, {"user_id": user_id})
        if trace:
            trace.add(PREFERENCES, {"user_id": user_id}, result, "procedural")
        preferences = {}
        for row in result.result_set:
            props = dict(row[0].properties)
            preferences[props.get("key", "")] = props.get("value", "")

        result = self.store.ro_query(user_id, PROCEDURES, {"user_id": user_id})
        if trace:
            trace.add(PROCEDURES, {"user_id": user_id}, result, "procedural")
        procedures = []
        for row in result.result_set:
            props = dict(row[0].properties)
            props["node_id"] = row[0].id
            procedures.append(props)

        return {
            "turns": turns,
            "facts": facts,
            "history": history,
            "preferences": preferences,
            "procedures": procedures,
            "matched": matched,
        }

    def think(
        self,
        user_id: str,
        query: str,
        trace=None,
        extra_context: str = "",
        ctx: dict | None = None,
    ) -> str:
        if ctx is None:
            ctx = self.build_context(user_id, query, trace)
        if ctx.get("history") and TEMPORAL_RE.search(query):
            for h in ctx["history"]:
                evo = h["evolution"]
                if len(evo) >= 2:
                    root = h["root"]
                    return (
                        f"Previously {evo[1]}, changed to {evo[0]} "
                        f"[fact: {root.get('subject', '?')} "
                        f"{root.get('predicate', '?')} {evo[0]}]"
                    )
        if ctx.get("procedures"):
            q = query.lower()
            completion = re.search(
                r"(finish(ed)?|done with|completed)", q
            )
            for p in ctx["procedures"]:
                steps = p.get("steps") or []
                if not steps:
                    continue
                name = str(p.get("name") or "")
                trigger = str(p.get("trigger") or "")
                if completion:
                    idx = -1
                    m = re.search(r"step\s*(\d+)", q)
                    if m:
                        idx = int(m.group(1)) - 1
                    else:
                        for i, s in enumerate(steps):
                            sl = str(s).lower()
                            if sl in q or (
                                len(sl) > 3
                                and any(w in q for w in sl.split() if len(w) > 3)
                            ):
                                idx = i
                                break
                    if idx < 0:
                        idx = len(steps) - 1
                    if idx + 1 < len(steps):
                        nxt = steps[idx + 1]
                        return f"{nxt[0].upper()}{nxt[1:]}."
                    return f"You have completed all the steps of {name}."
                name_toks = [
                    t for t in re.split(r"[-_\s]+", name.lower()) if len(t) > 2
                ]
                if (name_toks and all(t in q for t in name_toks)) or (
                    trigger and trigger.lower() in q
                ):
                    listed = " -> ".join(steps)
                    return (
                        f"Based on the recorded procedure for {name} "
                        f"(trigger: {trigger}), the steps are: {listed}."
                    )
        lines = ["Memory context:"]
        if extra_context:
            lines.append(extra_context)
        if ctx["preferences"]:
            lines.append("Preferences: " + "; ".join(f"{k}={v}" for k, v in ctx["preferences"].items()))
        for p in ctx.get("procedures", []):
            steps = " -> ".join(p.get("steps", []))
            lines.append(f"Procedure: {p.get('name')} (trigger: {p.get('trigger', '')}): {steps}")
        if ctx["facts"]:
            for f in ctx["facts"]:
                lines.append(f"Fact: {f.get('subject')} {f.get('predicate')} {f.get('value')}")
        for h in ctx.get("history", []):
            chain = " -> ".join(reversed(h["evolution"]))
            root = h["root"]
            lines.append(
                f"History: {root.get('subject', '?')} {root.get('predicate', '?')}: "
                f"{chain} (oldest to newest, last is current)"
            )
        for t in reversed(ctx["turns"]):
            lines.append(f"Turn ({t['role']}): {t['content']}")
        lines.append("")
        lines.append(f"Question: {query}")
        return self.llm.complete("\n".join(lines), system=SYSTEM_TEMPLATE.format(name=self.name))
