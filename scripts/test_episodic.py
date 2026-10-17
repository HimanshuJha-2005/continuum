import sys

sys.path.insert(0, "backend")

from app.falkor import GraphStore
from app.memory.episodic import EpisodicMemory

USER = "alice-test"


def main() -> int:
    store = GraphStore()
    store.query(USER, "MATCH (n) DETACH DELETE n")
    epi = EpisodicMemory(store)

    epi.start_session(USER, "s1")
    epi.add_turn(USER, "s1", "user", "I prefer TypeScript over JavaScript.")
    epi.add_turn(USER, "s1", "assistant", "Noted.")
    epi.start_session(USER, "s2")
    epi.add_turn(USER, "s2", "user", "What do I prefer?")

    sessions = epi.recent_sessions(USER)
    assert len(sessions) == 2, sessions
    assert sessions[0]["id"] == "s2", sessions
    turns = epi.session_turns(USER, "s1")
    assert [t["role"] for t in turns] == ["user", "assistant"], turns
    assert turns[0]["content"] == "I prefer TypeScript over JavaScript."

    print("episodic write/read OK")
    print("sessions:", sessions)
    return 0


if __name__ == "__main__":
    sys.exit(main())
