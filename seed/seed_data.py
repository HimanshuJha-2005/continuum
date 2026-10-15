USERS = [
    {"id": "alice", "name": "Alice"},
    {"id": "bob", "name": "Bob"},
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
]


def seed(store):
    raise NotImplementedError("Day 1: populate episodic + semantic + procedural stores")
