import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, "backend")

from app.falkor import GraphStore
from app.memory.episodic import EpisodicMemory
from app.memory.procedural import ProceduralMemory

USERS = 50
WORKERS = 32
READ_FACTS = """
MATCH (f:Fact)
WHERE any(w IN $words WHERE toLower(f.subject) CONTAINS w
          OR toLower(f.predicate) CONTAINS w
          OR toLower(f.value) CONTAINS w)
RETURN f
ORDER BY f.confidence DESC
LIMIT 5
"""
READ_TURNS = """
MATCH (u:User {id: $user_id})-[:HAS_SESSION]->(:Session)-[:CONTAINS]->(t:Turn)
RETURN t.role, t.content, t.ts
ORDER BY t.ts DESC, t.seq DESC
LIMIT 5
"""

store = GraphStore()


def worker(uid: str) -> list[tuple[str, float]]:
    epi = EpisodicMemory(store)
    proc = ProceduralMemory(store)
    timings: list[tuple[str, float]] = []

    def timed(label: str, fn) -> None:
        t0 = time.perf_counter()
        fn()
        timings.append((label, time.perf_counter() - t0))

    timed("write_turn", lambda: epi.add_turn(uid, "bench", "user", "benchmark message"))
    timed("write_pref", lambda: proc.record_preference(uid, "tool", "benchmark"))
    timed("read_facts", lambda: store.ro_query(uid, READ_FACTS, {"words": ["benchmark"]}))
    timed("read_turns", lambda: store.ro_query(uid, READ_TURNS, {"user_id": uid}))
    timed("read_prefs", lambda: proc.preferences(uid))
    return timings


def main() -> int:
    user_ids = [f"bench-{i}" for i in range(USERS)]
    for uid in user_ids:
        store.query(uid, "MATCH (n) DETACH DELETE n")
        EpisodicMemory(store).start_session(uid, "bench")

    t0 = time.perf_counter()
    all_timings: list[tuple[str, float]] = []
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        for result in pool.map(worker, user_ids):
            all_timings.extend(result)
    wall = time.perf_counter() - t0

    by_op: dict[str, list[float]] = {}
    for label, dt in all_timings:
        by_op.setdefault(label, []).append(dt)

    print(f"{USERS} tenants, {WORKERS} threads, {len(all_timings)} ops, {wall:.2f}s wall")
    print(f"throughput: {len(all_timings) / wall:.0f} ops/s")
    print(f"{'op':<12} {'n':>4} {'p50 ms':>8} {'p95 ms':>8} {'max ms':>8}")
    for label, samples in sorted(by_op.items()):
        samples.sort()
        p50 = statistics.median(samples) * 1000
        p95 = samples[int(len(samples) * 0.95) - 1] * 1000
        print(f"{label:<12} {len(samples):>4} {p50:>8.1f} {p95:>8.1f} {samples[-1] * 1000:>8.1f}")

    for uid in user_ids:
        store.query(uid, "MATCH (n) DETACH DELETE n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
