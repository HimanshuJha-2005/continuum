import sys

sys.path.insert(0, "backend")

from app.falkor import GraphStore
from app.memory.semantic import SemanticMemory

USER = "alice"


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

    print("semantic extract/recall/supersede OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
