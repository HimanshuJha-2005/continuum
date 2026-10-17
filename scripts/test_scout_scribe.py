import sys

sys.path.insert(0, "backend")

from app.agents.handoff import Handoff
from app.agents.scout import Scout
from app.agents.scribe import Scribe
from app.falkor import GraphStore
from app.memory.episodic import EpisodicMemory
from app.memory.semantic import SemanticMemory
from app.trace import Trace

USER = "alice-test"


def main() -> int:
    store = GraphStore()
    store.query(USER, "MATCH (n) DETACH DELETE n")
    store.query(USER, "MERGE (a:Agent {id: 'scout'}) MERGE (b:Agent {id: 'scribe'})")

    epi = EpisodicMemory(store)
    epi.start_session(USER, "s1")
    epi.add_turn(USER, "s1", "user", "We picked TypeScript for the frontend.")
    SemanticMemory(store).upsert_fact(
        USER,
        {"subject": "TypeScript", "predicate": "picked for", "value": "frontend", "confidence": 1.0},
    )
    SemanticMemory(store).upsert_fact(
        USER,
        {"subject": "TypeScript", "predicate": "offers", "value": "static types", "confidence": 1.0},
    )

    trace = Trace(turn_id="t-scout")
    scout = Scout(store)
    findings = scout.act(USER, "What stack did we pick?", trace=trace)
    assert "TypeScript" in findings, findings
    assert "Research report" in findings, findings
    assert "static types" in findings, "entity expansion did not surface linked facts"
    roles = [s.role for s in trace.steps]
    assert len(roles) >= 4, roles
    assert roles.count("semantic") >= 2, roles

    handoff = store.ro_query(
        USER,
        "MATCH (:Agent {id: 'scout'})-[h:HANDOFF_TO]->(:Agent {id: 'scribe'}) RETURN h.summary",
    ).result_set
    assert handoff and "What stack" in handoff[0][0], handoff

    trace2 = Trace(turn_id="t-scribe")
    scribe = Scribe(store)
    answer = scribe.act(USER, "What frontend stack did we settle on?", trace=trace2)
    assert isinstance(answer, str) and "TypeScript" in answer, answer

    read = store.ro_query(
        USER,
        "MATCH (:Agent {id: 'scribe'})-[:READ]->(:SharedState {key: 'research'}) RETURN count(*)",
    ).result_set[0][0]
    assert read >= 1, read

    statuses = store.ro_query(
        USER, "MATCH ()-[h:HANDOFF_TO]->() RETURN h.status"
    ).result_set
    assert statuses and all(r[0] == "consumed" for r in statuses), statuses

    handoffs = Handoff(store)
    unrelated_id = handoffs.create(
        USER, "scout", "scribe", "Researched penguin migration patterns"
    )
    stale = scribe.act(USER, "What is my favorite pizza?", trace=Trace(turn_id="t-stale"))
    assert isinstance(stale, str), stale
    assert "penguin" not in stale.lower(), f"irrelevant question received stale handoff: {stale}"
    still = handoffs.latest_for(USER, "scribe")
    assert still and still["id"] == unrelated_id, "irrelevant handoff was consumed anyway"

    print("scout findings:", findings)
    print("scribe answer:", answer[:250])
    print("scout->scribe handoff consumed + relevance gate + READ audit OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
