import sys

sys.path.insert(0, "backend")

from app.falkor import GraphStore
from app.memory.episodic import EpisodicMemory
from app.memory.semantic import SemanticMemory

USER = "alice-test"


def main() -> int:
    store = GraphStore()
    store.query(USER, "MATCH (n) DETACH DELETE n")
    sem = SemanticMemory(store)

    epi = EpisodicMemory(store)
    epi.start_session(USER, "s1")
    turn_id = epi.add_turn(USER, "s1", "user", "I use Python for backend services and TypeScript on the frontend.")

    extracted = sem.extract(
        USER, "I use Python for backend services and TypeScript on the frontend.",
        turn_id=turn_id,
    )
    assert extracted["facts"] or extracted["entities"], extracted
    print("extracted:", extracted["facts"])

    mentions = store.ro_query(
        USER,
        "MATCH (:Turn {id: $tid})-[:MENTIONS]->(:Entity) RETURN count(*)",
        {"tid": turn_id},
    ).result_set[0][0]
    assert mentions >= 1, f"MENTIONS edge missing after extraction: {mentions}"

    skipped = sem.extract(USER, "What is my favorite color?")
    assert skipped["facts"] == [] and skipped["entities"] == [], skipped
    assert skipped.get("skipped") is True, skipped

    from app.memory.semantic import QUESTION_RE

    question_cases = [
        "What language do I prefer",          # no question mark
        "Tell me what my deploy target is",   # imperative, no question mark
        "when did we switch databases",       # lowercase wh, no mark
        "Show me how the memory works",       # imperative show
        "What is my favorite color?",         # classic
        "Do I still use AWS?",                # aux-led with mark
    ]
    statement_cases = [
        "I prefer TypeScript for new projects",
        "We now deploy to GCP",               # update must still extract
        "Can you update my deploy target to GCP?",  # request carrying an update
        "Always answer in short bullets",
    ]
    for q in question_cases:
        assert QUESTION_RE.match(q), f"question not skipped: {q}"
    for s in statement_cases:
        assert not QUESTION_RE.match(s), f"statement wrongly skipped: {s}"

    prefs = sem.extract(USER, "Always answer me in short bullet points only.")
    assert prefs.get("preferences"), f"preference not extracted: {prefs}"
    recorded = store.ro_query(
        USER,
        "MATCH (u:User {id: 'alice-test'})-[:PREFERS]->(p:Preference) RETURN count(*)",
    ).result_set[0][0]
    assert recorded >= 1, "preference node not recorded from chat extraction"

    sem.upsert_fact(
        USER,
        {"subject": "Python", "predicate": "used for", "value": "backend services", "confidence": 1.0},
    )
    hits = sem.recall(USER, "python")
    assert len(hits) >= 1, hits
    old = hits[0]
    print("recall hit:", old["subject"], old["predicate"], old["value"])

    new_id = sem.supersede(
        USER,
        old["id"],
        {
            "subject": old["subject"],
            "predicate": old["predicate"],
            "value": "Rust",
            "confidence": 0.95,
        },
    )
    after = sem.recall(USER, "rust")
    assert any(f["id"] == new_id for f in after), after

    sem.upsert_fact(
        USER,
        {"subject": "Go", "predicate": "used for", "value": "backend services", "confidence": 0.8},
    )
    conflict_id = sem.upsert_fact(
        USER,
        {"subject": "Go", "predicate": "used for", "value": "data pipelines", "confidence": 0.9},
    )
    superseded = store.ro_query(
        USER,
        """
        MATCH (n:Fact {id: $id})-[:SUPERSEDES]->(o:Fact)
        RETURN o.id, o.valid_to
        """,
        {"id": conflict_id},
    ).result_set
    assert superseded, "conflicting upsert did not supersede"
    assert superseded[0][1] is not None, "old fact missing valid_to"
    both = store.ro_query(
        USER,
        """
        MATCH (f:Fact {subject: 'Go', predicate: 'used for'})
        RETURN count(*)
        """,
    ).result_set[0][0]
    assert both == 2, f"expected old + new fact chain, got {both}"
    dupes = store.ro_query(
        USER,
        """
        MATCH (f:Fact)
        WITH f.id AS fid, count(*) AS c
        WHERE c > 1
        RETURN fid, c
        """,
    ).result_set
    assert not dupes, f"duplicate fact nodes: {dupes}"
    bare = store.ro_query(
        USER,
        "MATCH (f:Fact) WHERE f.subject IS NULL RETURN f.id",
    ).result_set
    assert not bare, f"bare fact nodes: {bare}"

    print("semantic extract/recall/supersede OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
