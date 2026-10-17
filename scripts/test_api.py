"""API integration tests — exercises the real FastAPI /chat endpoint in-process.

These catch wiring bugs the unit suites cannot (e.g. a live web chat never
persisting turns because the default session node did not exist yet).
"""

import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from app.falkor import GraphStore
from app.main import app

USER = f"api-test-{uuid.uuid4().hex[:8]}"


def chat(client: TestClient, message: str) -> dict:
    """POST /chat, retrying on transient LLM rate limits."""
    last = None
    for attempt in range(3):
        res = client.post("/chat", json={"user_id": USER, "message": message})
        assert res.status_code == 200, res.text
        body = res.json()
        if not (body.get("extracted") or {}).get("error"):
            return body
        last = body
        time.sleep(15)
    raise AssertionError(f"extraction kept failing: {last}")


def main() -> int:
    client = TestClient(app)
    store = GraphStore()

    health = client.get("/health")
    assert health.status_code == 200, health.text
    assert health.json()["falkordb"] == "up", health.json()

    # 1. Live web chat on a brand-new user (no seed, no explicit session)
    body = chat(client, "I use Postgres for the persistence layer.")
    assert body["turn_id"], body
    assert body["answer"], body
    assert "extracted" in body and "trace" in body, body

    # 2. Turns and the default session must exist even without seed_data
    g = store.user_graph(USER)
    sessions = g.query("MATCH (s:Session) RETURN s.id").result_set
    assert sessions and sessions[0][0] == "web", sessions
    turns = g.query("MATCH (t:Turn) RETURN t.role, t.content").result_set
    roles = [r[0] for r in turns]
    assert roles == ["user", "assistant"], turns
    contains = g.query("MATCH (s:Session)-[:CONTAINS]->(t:Turn) RETURN count(t)").result_set
    assert contains[0][0] == 2, contains

    # 3. Provenance edges depend on the turn node — DERIVED must exist
    derived = g.query("MATCH (:Turn)-[:DERIVED]->(:Fact) RETURN count(*)").result_set
    if body["extracted"].get("facts", 0) > 0:
        assert derived[0][0] >= 1, ("DERIVED missing despite extraction", body["extracted"])
    mentions = g.query("MATCH (:Turn)-[:MENTIONS]->(:Entity) RETURN count(*)").result_set
    if body["extracted"].get("entities", 0) > 0:
        assert mentions[0][0] >= 1, ("MENTIONS missing despite extraction", body["extracted"])
    facts = g.query("MATCH (f:Fact) RETURN f.subject, f.predicate, f.value").result_set
    print("facts:", facts)
    print("derived:", derived[0][0], "mentions:", mentions[0][0])

    # 4. A pure question is skipped for extraction but still answers
    body2 = chat(client, "What do I use for the persistence layer?")
    assert body2["extracted"].get("skipped") is True, body2["extracted"]
    assert "Postgres" in body2["answer"], body2["answer"]
    turns2 = g.query("MATCH (t:Turn) RETURN count(t)").result_set
    assert turns2[0][0] >= 4, turns2

    # 5. History / temporal: supersession must be walkable after an update.
    # LLM extraction phrasing varies, so retry with clearer phrasings.
    chain = []
    for msg in (
        "Update: we use CockroachDB for the persistence layer now.",
        "Update: our persistence layer is now CockroachDB, not Postgres.",
        "Update: change the persistence layer from Postgres to CockroachDB.",
    ):
        chat(client, msg)
        chain = g.query(
            "MATCH (n:Fact)-[:SUPERSEDES]->(old:Fact) RETURN n.value, old.value, old.valid_to"
        ).result_set
        if chain:
            break
    assert chain, "no SUPERSEDES edge after update messages"
    assert chain[0][1] != chain[0][0] and chain[0][2] is not None, chain
    # invariant: at most one active fact per subject + predicate head
    active = g.query(
        "MATCH (f:Fact) WHERE f.valid_to IS NULL RETURN f.subject, f.predicate, f.value"
    ).result_set
    heads = {}
    for subj, pred, _ in active:
        key = (subj, str(pred).split(" ")[0].rstrip("s"))
        heads.setdefault(key, []).append(pred)
    dupes = {k: v for k, v in heads.items() if len(v) > 1}
    assert not dupes, ("invariant broken: parallel active facts", dupes, active)
    print("supersession chain:", chain)

    # 6. Isolation: nothing leaked into the seeded demo users
    alice = store.user_graph("alice").query(
        "MATCH (f:Fact) WHERE f.value = 'CockroachDB' RETURN count(f)"
    ).result_set
    assert alice[0][0] == 0, alice

    # cleanup this test user's graph
    store.user_graph(USER).query("MATCH (n) DETACH DELETE n")
    print("api integration OK for", USER)
    return 0


if __name__ == "__main__":
    sys.exit(main())
