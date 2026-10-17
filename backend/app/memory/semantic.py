import json
import re
import uuid

from app.llm import get_llm
from app.memory.procedural import ProceduralMemory

EXTRACT_SYSTEM = "You extract structured memory from text. Respond with JSON only."
EXTRACT_PROMPT = """Extract entities, facts, and preferences from the text below.

Rules:
- entities: up to 5 objects with "name" and "type" (type is a short noun: person, language, project, place, org, etc.)
- facts: up to 5 objects with "subject", "predicate", "value", "confidence" (confidence between 0.0 and 1.0)
- preferences: up to 3 objects with "key" and "value" for explicit statements of how the user wants things
  done or to be addressed (e.g. "always answer in short bullets" -> {{"key": "answer_style", "value": "short bullets"}}).
  Use short snake_case keys. Empty list if the text states no preference.
- Write facts in third person. The subject must be a concrete name or noun (Python, Alice, Continuum) — never a pronoun like "I", "we", or a placeholder like "User".
- The predicate must be a short verb phrase such as "uses for", "prefers", "deploys to".
- Only extract what is stated or clearly implied. Do not invent.
- If the text is only a question asking what is true, return empty lists for all fields.

Text: {text}

JSON:"""

QUESTION_RE = re.compile(
    r"^\s*(?:what|when|where|which|who|whom|whose|how|why|is|are|was|were"
    r"|do|does|did|can|could|would|should|will|has|have|had)\b[^?]*\?\s*$",
    re.I,
)


def _parse_json(raw: str) -> dict:
    cleaned = re.sub(r"```(?:json)?", "", raw).strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"no JSON object in LLM response: {raw!r}")
    return json.loads(cleaned[start : end + 1])


class SemanticMemory:
    """Facts and entities extracted from conversation, linked in the graph."""

    def __init__(self, store, llm=None):
        self.store = store
        self.llm = llm

    def _chat(self, prompt: str, system: str = "") -> str:
        return (self.llm or get_llm()).complete(prompt, system=system)

    def extract(self, user_id: str, text: str, turn_id: str | None = None) -> dict:
        if QUESTION_RE.match(text):
            return {
                "entities": [],
                "facts": [],
                "preferences": [],
                "fact_ids": [],
                "skipped": True,
            }
        prompt = EXTRACT_PROMPT.format(text=text)
        for attempt in range(2):
            try:
                data = _parse_json(self._chat(prompt, system=EXTRACT_SYSTEM))
                break
            except (ValueError, json.JSONDecodeError):
                if attempt == 1:
                    raise
        entities = data.get("entities") or []
        facts = data.get("facts") or []
        preferences = data.get("preferences") or []
        for e in entities:
            self._upsert_entity(user_id, e.get("name", ""), e.get("type", ""), turn_id=turn_id)
        for p in preferences:
            key = re.sub(r"[^a-z0-9_]+", "_", str(p.get("key", "")).strip().lower()).strip("_")[:40]
            value = str(p.get("value", "")).strip()[:200]
            if key and value:
                ProceduralMemory(self.store).record_preference(user_id, key, value)
        fact_ids = [
            self.upsert_fact(
                user_id,
                {
                    "subject": f.get("subject", ""),
                    "predicate": re.sub(
                        r"^(is|are|was|were)\s+", "", f.get("predicate", "")
                    ).strip(),
                    "value": f.get("value", ""),
                    "confidence": float(f.get("confidence", 0.5)),
                },
                turn_id=turn_id,
            )
            for f in facts
        ]
        return {
            "entities": entities,
            "facts": facts,
            "preferences": preferences,
            "fact_ids": fact_ids,
        }

    def _upsert_entity(
        self, user_id: str, name: str, type_: str, turn_id: str | None = None
    ) -> None:
        if not name:
            return
        self.store.query(
            user_id,
            """
            MERGE (e:Entity {name: $name})
            SET e.type = $type
            """,
            {"name": name, "type": type_},
        )
        if turn_id:
            self.store.query(
                user_id,
                """
                MATCH (t:Turn {id: $turn_id})
                MATCH (e:Entity {name: $name})
                MERGE (t)-[:MENTIONS]->(e)
                """,
                {"turn_id": turn_id, "name": name},
            )

    def upsert_fact(
        self, user_id: str, fact: dict, turn_id: str | None = None
    ) -> str:
        existing = self.store.ro_query(
            user_id,
            """
            MATCH (f:Fact {subject: $subject, predicate: $predicate})
            WHERE f.value <> $value
            AND f.valid_to IS NULL
            RETURN f.id
            """,
            {"subject": fact["subject"], "predicate": fact["predicate"], "value": fact["value"]},
        )
        if existing.result_set:
            stored_id = fact.get("fact_id") or str(uuid.uuid4())
            for row in existing.result_set:
                stored_id = self.supersede(user_id, row[0], fact)
        else:
            fact_id = str(uuid.uuid4())
            result = self.store.query(
                user_id,
                """
                MERGE (subj:Entity {name: $subject})
                ON CREATE SET subj.type = 'concept'
                MERGE (f:Fact {subject: $subject, predicate: $predicate, value: $value})
                ON CREATE SET f.id = $fact_id, f.confidence = $confidence, f.valid_from = timestamp()
                ON MATCH SET f.last_seen = timestamp(), f.confidence = $confidence, f.valid_to = NULL
                MERGE (subj)-[:RELATES {predicate: $predicate}]->(f)
                RETURN f.id
                """,
                {
                    "subject": fact["subject"],
                    "predicate": fact["predicate"],
                    "value": fact["value"],
                    "confidence": fact.get("confidence", 0.5),
                    "fact_id": fact_id,
                },
            )
            stored_id = result.result_set[0][0]
        if turn_id:
            self.store.query(
                user_id,
                """
                MATCH (t:Turn {id: $turn_id})
                MATCH (f:Fact {id: $fact_id})
                CREATE (t)-[:DERIVED {ts: timestamp()}]->(f)
                """,
                {"turn_id": turn_id, "fact_id": stored_id},
            )
        return stored_id

    def recall(self, user_id: str, query: str, limit: int = 10) -> list[dict]:
        result = self.store.ro_query(
            user_id,
            """
            MATCH (f:Fact)
            WHERE (toLower(f.subject) CONTAINS toLower($q)
                OR toLower(f.predicate) CONTAINS toLower($q)
                OR toLower(f.value) CONTAINS toLower($q))
            AND f.valid_to IS NULL
            RETURN f
            ORDER BY f.confidence DESC
            LIMIT $limit
            """,
            {"q": query, "limit": limit},
        )
        facts = []
        for row in result.result_set:
            node = row[0]
            props = dict(node.properties)
            props["node_id"] = node.id
            facts.append(props)
        return facts

    def supersede(self, user_id: str, old_fact_id: str, new_fact: dict) -> str:
        new_id = str(uuid.uuid4())
        result = self.store.query(
            user_id,
            """
            MATCH (old:Fact {id: $old_id})
            SET old.valid_to = timestamp()
            MERGE (n:Fact {
                subject: $subject,
                predicate: $predicate,
                value: $value
            })
            ON CREATE SET
                n.id = $new_id,
                n.confidence = $confidence,
                n.valid_from = timestamp()
            ON MATCH SET
                n.last_seen = timestamp(),
                n.confidence = $confidence,
                n.valid_to = NULL
            MERGE (n)-[:SUPERSEDES]->(old)
            RETURN n.id
            """,
            {
                "old_id": old_fact_id,
                "new_id": new_id,
                "subject": new_fact["subject"],
                "predicate": new_fact["predicate"],
                "value": new_fact["value"],
                "confidence": new_fact.get("confidence", 0.9),
            },
        )
        stored_id = result.result_set[0][0]
        self.store.query(
            user_id,
            """
            MATCH (s:Entity {name: $subject})-[:RELATES]->(:Fact {id: $old_id})
            MATCH (n:Fact {id: $stored_id})
            MERGE (s)-[:RELATES {predicate: $predicate}]->(n)
            """,
            {
                "subject": new_fact["subject"],
                "predicate": new_fact["predicate"],
                "old_id": old_fact_id,
                "stored_id": stored_id,
            },
        )
        return stored_id
