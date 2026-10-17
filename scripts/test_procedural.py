import sys

sys.path.insert(0, "backend")

from app.falkor import GraphStore
from app.memory.procedural import ProceduralMemory

USER = "alice-test"


def main() -> int:
    store = GraphStore()
    store.query(USER, "MATCH (n) DETACH DELETE n")
    proc = ProceduralMemory(store)

    proc.record_preference(USER, "language", "TypeScript")
    proc.record_preference(USER, "language", "Rust")
    prefs = proc.preferences(USER)
    assert prefs == {"language": "Rust"}, prefs

    proc.record_procedure(
        USER,
        "deploy-backend",
        ["build image", "push to registry", "rollout"],
        trigger="release",
    )
    procs = proc.procedures(USER, trigger="release")
    assert len(procs) == 1 and procs[0]["name"] == "deploy-backend", procs
    assert proc.procedures(USER, trigger="other") == []

    print("procedural write/read OK")
    print("prefs:", prefs)
    return 0


if __name__ == "__main__":
    sys.exit(main())
