import sys

sys.path.insert(0, "backend")

from app.falkor import GraphStore
from app.memory.semantic import SemanticMemory

USER = "alice-test"


def main() -> int:
    store = GraphStore()
    store.query(USER, "MATCH (n) DETACH DELETE n")
    sem = SemanticMemory(store)

    extracted = sem.extract(
        USER, "I use Python for backend services and TypeScript on the frontend."
    )
    assert extracted["facts"] or extracted["entities"], extracted
    print("extracted:", extracted["facts"])

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

    print("semantic extract/recall/supersede OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
