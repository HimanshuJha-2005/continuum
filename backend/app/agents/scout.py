from app.agents.base import Agent
from app.agents.handoff import Handoff

STATE_KEY = "research"


class Scout(Agent):
    """Researcher: explores the graph, publishes findings to shared state, hands off to Scribe."""

    def __init__(self, store, llm=None):
        super().__init__("scout", "Scout", "researcher", store, llm)

    def act(self, user_id: str, query: str, trace=None) -> str:
        ctx = self.build_context(user_id, query, trace)
        if ctx["facts"]:
            findings = "\n".join(
                f"- {f.get('subject')} {f.get('predicate')} {f.get('value')}"
                for f in ctx["facts"]
            )
        else:
            findings = "- no facts matched"
        handoffs = Handoff(self.store)
        handoffs.set_shared_state(user_id, STATE_KEY, findings, self.agent_id)
        summary = (
            f"Researched '{query}': {len(ctx['facts'])} facts, "
            f"{len(ctx['turns'])} recent turns"
        )
        handoffs.create(user_id, self.agent_id, "scribe", summary)
        return findings
