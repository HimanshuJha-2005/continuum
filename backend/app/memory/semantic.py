import json
import re
import uuid

from app.llm import get_llm

EXTRACT_SYSTEM = "You extract structured memory from text. Respond with JSON only."
EXTRACT_PROMPT = """Extract entities and facts from the text below.

Rules:
- entities: up to 5 objects with "name" and "type" (type is a short noun: person, language, project, place, org, etc.)
- facts: up to 5 objects with "subject", "predicate", "value", "confidence" (confidence between 0.0 and 1.0)
- Write facts in third person. The subject must be a concrete name or noun (Python, Alice, Continuum) — never a pronoun like "I", "we", or a placeholder like "User".
- The predicate must be a short verb phrase such as "uses for", "prefers", "deploys to".
- Only extract what is stated or clearly implied. Do not invent.

Text: {text}

JSON:"""


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
        for e in entities:
            self._upsert_entity(user_id, e.get("name", ""), e.get("type", ""))
        fact_ids = [
            self.upsert_fact(
                user_id,
                {
                    "subject": f.get("subject", ""),
                    "predicate": f.get("predicate", ""),
                    "value": f.get("value", ""),
                    "confidence": float(f.get("confidence", 0.5)),
                },
                turn_id=turn_id,
            )
            for f in facts
        ]
        return {"entities": entities, "facts": facts, "fact_ids": fact_ids}

    def _upsert_entity(self, user_id: str, name: str, type_: str) -> None:
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

    def upsert_fact(
        self, user_id: str, fact: dict, turn_id: str | None = None
    ) -> str:
        existing = self.store.ro_query(
            user_id,
            """
            MATCH (f:Fact {subject: $subject, predicate: $predicate})
            WHERE f.value <> $value
            RETURN f.id
            LIMIT 1
            """,
            {"subject": fact["subject"], "predicate": fact["predicate"], "value": fact["value"]},
        )
        if existing.result_set:
            stored_id = self.supersede(user_id, existing.result_set[0][0], fact)
        else:
            fact_id = str(uuid.uuid4())
            result = self.store.query(
                user_id,
                """
                MERGE (subj:Entity {name: $subject})
                ON CREATE SET subj.type = 'concept'
                MERGE (f:Fact {subject: $subject, predicate: $predicate, value: $value})
                ON CREATE SET f.id = $fact_id, f.confidence = $confidence, f.valid_from = timestamp()
                ON MATCH SET f.last_seen = timestamp(), f.confidence = $confidence
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
            WHERE toLower(f.subject) CONTAINS toLower($q)
               OR toLower(f.predicate) CONTAINS toLower($q)
               OR toLower(f.value) CONTAINS toLower($q)
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
        self.store.query(
            user_id,
            """
            MATCH (old:Fact {id: $old_id})
            SET old.valid_to = timestamp()
            CREATE (n:Fact {
                id: $new_id,
                subject: $subject,
                predicate: $predicate,
                value: $value,
                confidence: $confidence,
                valid_from: timestamp()
            })
            CREATE (n)-[:SUPERSEDES]->(old)
            WITH n
            MATCH (s:Entity {name: $subject})-[:RELATES]->(:Fact {id: $old_id})
            MERGE (s)-[:RELATES {predicate: $predicate}]->(n)
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
        return new_id
