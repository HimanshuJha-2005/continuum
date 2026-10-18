from app.falkor import GraphStore
from app.memory.episodic import EpisodicMemory
from app.memory.procedural import ProceduralMemory
from app.memory.semantic import SemanticMemory

USERS = [
    {"id": "alice", "name": "Alice"},
    {"id": "bob", "name": "Bob"},
]

AGENTS = [
    {"id": "scout", "name": "Scout", "role": "retriever"},
    {"id": "scribe", "name": "Scribe", "role": "summarizer"},
]

SAMPLE_SESSIONS = [
    {
        "user_id": "alice",
        "session_id": "s1",
        "turns": [
            {"role": "user", "content": "I prefer TypeScript over JavaScript for new projects."},
            {"role": "assistant", "content": "Noted — I'll default to TypeScript for your new projects."},
        ],
    },
    {
        "user_id": "alice",
        "session_id": "s2",
        "turns": [
            {"role": "user", "content": "Remember the API design doc we discussed for Project Continuum?"},
            {"role": "assistant", "content": "Yes — last session we sketched a FastAPI backend with FalkorDB memory."},
        ],
    },
    {
        "user_id": "bob",
        "session_id": "b1",
        "turns": [
            {"role": "user", "content": "My deploy target is AWS Lambda."},
            {"role": "assistant", "content": "Got it — deployments will target AWS Lambda."},
        ],
    },
]

FACTS = [
    {
        "user_id": "alice",
        "fact": {
            "subject": "TypeScript",
            "predicate": "preferred for",
            "value": "new projects",
            "confidence": 1.0,
        },
    },
    {
        "user_id": "alice",
        "fact": {
            "subject": "Continuum",
            "predicate": "uses",
            "value": "FastAPI backend with FalkorDB memory",
            "confidence": 1.0,
        },
    },
    {
        "user_id": "bob",
        "fact": {
            "subject": "Bob",
            "predicate": "deploys to",
            "value": "AWS Lambda",
            "confidence": 1.0,
        },
    },
]

PREFERENCES = [
    ("alice", "language", "TypeScript"),
    ("alice", "editor", "VS Code"),
    ("bob", "language", "Go"),
]

PROCEDURES = [
    ("alice", "deploy-preview", ["Build", "run tests", "push branch", "open PR"], "release"),
]


def seed(store, reset: bool = True) -> dict:
    epi = EpisodicMemory(store)
    proc = ProceduralMemory(store)
    sem = SemanticMemory(store)

    if reset:
        for u in USERS:
            store.query(u["id"], "MATCH (n) DETACH DELETE n")

    for user in USERS:
        for agent in AGENTS:
            store.query(
                user["id"],
                """
                MERGE (a:Agent {id: $id})
                SET a.name = $name, a.role = $role
                """,
                agent,
            )

    for session in SAMPLE_SESSIONS:
        epi.start_session(session["user_id"], session["session_id"])
        for turn in session["turns"]:
            epi.add_turn(
                session["user_id"], session["session_id"], turn["role"], turn["content"]
            )

    for entry in FACTS:
        sem.upsert_fact(entry["user_id"], entry["fact"])

    for user_id, key, value in PREFERENCES:
        proc.record_preference(user_id, key, value)

    for user_id, name, steps, trigger in PROCEDURES:
        proc.record_procedure(user_id, name, steps, trigger)

    return {
        "users": len(USERS),
        "agents": len(AGENTS),
        "sessions": len(SAMPLE_SESSIONS),
        "facts": len(FACTS),
        "preferences": len(PREFERENCES),
        "procedures": len(PROCEDURES),
    }


def main() -> int:
    store = GraphStore()
    counts = seed(store)
    print("seeded:", counts)
    return 0
