import sys
from unittest.mock import MagicMock

sys.path.insert(0, "backend")

from app.agents.base import Agent, significant_words, TEMPORAL_RE, chain_matches_words


class DummyLLM:
    def complete(self, prompt: str, system: str = "") -> str:
        return "LLM_FALLTHROUGH_OK"


def test_chain_matches_words():
    editor_root = {"subject": "user", "predicate": "prefers_editor", "value": "Cursor"}
    editor_evo = ["Cursor", "VS Code"]

    # 1. Non-temporal topic words match
    words = significant_words("What editor did I use before?")
    assert chain_matches_words(editor_root, editor_evo, words) is True

    # 2. Topic words do not match (even though 'first' and 'was' are in the question)
    unrelated_words = significant_words("What was the name of my first project?")
    assert chain_matches_words(editor_root, editor_evo, unrelated_words) is False

    # 3. Empty words return False
    assert chain_matches_words(editor_root, editor_evo, []) is False


def test_unrelated_temporal_query_falls_through():
    """Asking 'What was the name of my first project?' must NOT return editor history."""
    store = MagicMock()
    llm = DummyLLM()
    agent = Agent("test", "TestAgent", "assistant", store, llm=llm)

    ctx = {
        "turns": [],
        "facts": [],
        "preferences": {},
        "procedures": [],
        "history": [
            {
                "root": {"subject": "user", "predicate": "prefers_editor", "value": "Cursor"},
                "evolution": ["Cursor", "VS Code"],
            }
        ],
    }

    # Query has temporal words ('was', 'first') but topic words ('name', 'project') do NOT match editor
    query = "What was the name of my first project?"
    res = agent.think("u1", query, ctx=ctx)
    print("Result for unrelated query:", res)
    assert res == "LLM_FALLTHROUGH_OK", f"Expected LLM fallthrough, got: {res}"


def test_matching_temporal_query_returns_chain():
    """Asking 'What editor did I use before?' SHOULD return editor history."""
    store = MagicMock()
    llm = DummyLLM()
    agent = Agent("test", "TestAgent", "assistant", store, llm=llm)

    ctx = {
        "turns": [],
        "facts": [],
        "preferences": {},
        "procedures": [],
        "history": [
            {
                "root": {"subject": "user", "predicate": "prefers_editor", "value": "Cursor"},
                "evolution": ["Cursor", "VS Code"],
            }
        ],
    }

    query = "What editor did I use before?"
    res = agent.think("u1", query, ctx=ctx)
    print("Result for matching query:", res)
    assert "Previously VS Code, changed to Cursor" in res, f"Expected chain match, got: {res}"


def test_multiple_chains_picks_relevant_one():
    """If multiple chains exist, pick the chain matching the query, not just the first one."""
    store = MagicMock()
    llm = DummyLLM()
    agent = Agent("test", "TestAgent", "assistant", store, llm=llm)

    ctx = {
        "turns": [],
        "facts": [],
        "preferences": {},
        "procedures": [],
        "history": [
            {
                "root": {"subject": "user", "predicate": "prefers_editor", "value": "Cursor"},
                "evolution": ["Cursor", "VS Code"],
            },
            {
                "root": {"subject": "Continuum", "predicate": "database", "value": "FalkorDB"},
                "evolution": ["FalkorDB", "RedisGraph"],
            },
        ],
    }

    query = "What database was used before?"
    res = agent.think("u1", query, ctx=ctx)
    print("Result for database query:", res)
    assert "Previously RedisGraph, changed to FalkorDB" in res, f"Expected database chain, got: {res}"


def test_build_context_filters_unrelated_history():
    """build_context must only include history chains relevant to query keywords."""
    store = MagicMock()
    # Mock store queries: RECENT_TURNS, FULLTEXT_FACTS, FACT_MATCH, HISTORY_CHAINS, PREFERENCES, PROCEDURES
    class MockNode:
        def __init__(self, props, node_id=1):
            self.properties = props
            self.id = node_id

    class MockQueryResult:
        def __init__(self, rows):
            self.result_set = rows

    def mock_ro_query(user_id, query_str, params):
        if "SUPERSEDES" in query_str:
            # Return editor chain and database chain
            root_editor = MockNode({"subject": "user", "predicate": "prefers_editor", "value": "Cursor"})
            evo_editor = ["Cursor", "VS Code"]
            root_db = MockNode({"subject": "Continuum", "predicate": "database", "value": "FalkorDB"})
            evo_db = ["FalkorDB", "RedisGraph"]
            return MockQueryResult([[root_editor, evo_editor], [root_db, evo_db]])
        return MockQueryResult([])

    store.ro_query.side_effect = mock_ro_query
    agent = Agent("test", "TestAgent", "assistant", store, llm=DummyLLM())

    # 1. Unrelated query: history should be empty
    ctx_unrelated = agent.build_context("u1", "What was the name of my first project?")
    assert len(ctx_unrelated["history"]) == 0, f"Expected 0 history chains, got: {ctx_unrelated['history']}"

    # 2. Database query: history should only contain the database chain
    ctx_db = agent.build_context("u1", "What database was used before?")
    assert len(ctx_db["history"]) == 1
    assert ctx_db["history"][0]["root"]["predicate"] == "database"


if __name__ == "__main__":
    test_chain_matches_words()
    print("PASS: test_chain_matches_words")

    test_unrelated_temporal_query_falls_through()
    print("PASS: test_unrelated_temporal_query_falls_through")

    test_matching_temporal_query_returns_chain()
    print("PASS: test_matching_temporal_query_returns_chain")

    test_multiple_chains_picks_relevant_one()
    print("PASS: test_multiple_chains_picks_relevant_one")

    test_build_context_filters_unrelated_history()
    print("PASS: test_build_context_filters_unrelated_history")
    print("\nALL 5 TESTS PASSED SUCCESSFULLY!")
