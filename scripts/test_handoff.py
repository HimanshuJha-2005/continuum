import sys

sys.path.insert(0, "backend")

from app.agents.handoff import Handoff
from app.falkor import GraphStore

USER = "alice"
OTHER = "bob"


def main() -> int:
    store = GraphStore()
    store.query(USER, "MATCH (n) DETACH DELETE n")
    store.query(OTHER, "MATCH (n) DETACH DELETE n")
    for uid in (USER, OTHER):
        for aid in ("scout", "scribe"):
            store.query(uid, "MERGE (a:Agent {id: $id})", {"id": aid})

    h = Handoff(store)

    h.set_shared_state(USER, "research", "FalkorDB uses Redis protocol", "scout")
    value = h.shared_state(USER, "research", agent_id="scribe")
    assert value == "FalkorDB uses Redis protocol", value

    readonly = h.shared_state(USER, "research")
    assert readonly == value

    assert h.shared_state(OTHER, "research") is None, "isolation broken"

    wrote = store.ro_query(
        USER, "MATCH (:Agent {id: 'scout'})-[:WROTE]->(:SharedState {key: 'research'}) RETURN count(*)"
    ).result_set[0][0]
    read = store.ro_query(
        USER, "MATCH (:Agent {id: 'scribe'})-[:READ]->(:SharedState {key: 'research'}) RETURN count(*)"
    ).result_set[0][0]
    assert wrote == 1 and read == 1, (wrote, read)

    h.create(USER, "scout", "scribe", "Found FalkorDB uses Redis protocol")
    latest = h.latest_for(USER, "scribe")
    assert latest and latest["from"] == "scout", latest
    assert h.latest_for(USER, "scout") is None

    print("handoff create/latest OK, shared state set/get OK, WROTE/READ edges OK, isolation OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
