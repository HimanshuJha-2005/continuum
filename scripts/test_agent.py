import sys

sys.path.insert(0, "backend")

from app.agents.base import Agent, significant_words
from app.falkor import GraphStore
from app.memory.episodic import EpisodicMemory
from app.memory.procedural import ProceduralMemory
from app.memory.semantic import SemanticMemory
from app.trace import Trace

USER = "alice-test"


def main() -> int:
    store = GraphStore()
    store.query(USER, "MATCH (n) DETACH DELETE n")

    epi = EpisodicMemory(store)
    epi.start_session(USER, "s1")
    epi.add_turn(USER, "s1", "user", "I prefer TypeScript for frontend work.")
    epi.add_turn(USER, "s1", "assistant", "Noted.")

    ProceduralMemory(store).record_preference(USER, "language", "TypeScript")
    SemanticMemory(store).upsert_fact(
        USER,
        {"subject": "TypeScript", "predicate": "used for", "value": "frontend work", "confidence": 1.0},
    )

    trace = Trace(turn_id="t-test")
    agent = Agent("scribe", "Scribe", "summarizer", store)
    answer = agent.think(USER, "What language do I prefer for frontend work?", trace=trace)

    assert isinstance(answer, str) and len(answer) > 10, answer
    assert len(trace.steps) >= 3, [s.role for s in trace.steps]
    roles = [s.role for s in trace.steps]
    assert "episodic" in roles and "semantic" in roles and "procedural" in roles, roles

    assert significant_words("Do I use Go?") == ["use", "go"], significant_words("Do I use Go?")
    assert significant_words("What about my API key?") == ["api", "key"], significant_words("What about my API key?")
    assert significant_words("What?") == [], significant_words("What?")

    print("roles traced:", roles)
    print("answer:", answer[:300])
    return 0


if __name__ == "__main__":
    sys.exit(main())
