import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))

from app.agents.base import Agent
from app.falkor import GraphStore
from app.memory.episodic import EpisodicMemory
from app.memory.procedural import ProceduralMemory
from app.memory.semantic import SemanticMemory

USER = "alice"
OTHER = "bob"


def wait_for_falkor(timeout: float = 45.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            GraphStore().ro_query(USER, "RETURN 1", {})
            return
        except Exception:
            time.sleep(1.5)
    raise TimeoutError("FalkorDB did not come back in time")


def snapshot(store) -> dict:
    epi = EpisodicMemory(store)
    sem = SemanticMemory(store)
    proc = ProceduralMemory(store)
    return {
        "turns": len(epi.session_turns(USER, "s1")),
        "sessions": len(epi.recent_sessions(USER)),
        "facts": len(sem.recall(USER, "TypeScript")),
        "prefs": proc.preferences(USER),
        "procedures": len(proc.procedures(USER)),
        "other_facts": len(sem.recall(OTHER, "TypeScript")),
        "other_prefs": proc.preferences(OTHER),
    }


def main() -> int:
    from seed.seed_data import seed

    store = GraphStore()
    seed(store)
    before = snapshot(store)
    assert before["turns"] == 2, before
    assert before["facts"] >= 1, before
    assert before["prefs"].get("language") == "TypeScript", before
    assert before["other_facts"] == 0, before
    print("before restart:", before)

    print("restarting falkordb...")
    subprocess.run(
        ["docker", "compose", "restart", "falkordb"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    wait_for_falkor()

    store = GraphStore()
    after = snapshot(store)
    assert after == before, (before, after)
    print("after restart:", after)

    agent = Agent("scribe", "Scribe", "summarizer", store)
    answer = agent.think(USER, "What language do I prefer?", trace=None)
    assert "TypeScript" in answer, answer
    print("agent after restart:", answer[:200])

    print("restart persistence + isolation OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
