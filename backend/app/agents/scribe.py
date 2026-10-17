from app.agents.base import Agent, significant_words
from app.agents.handoff import Handoff
from app.agents.scout import STATE_KEY


class Scribe(Agent):
    """Summarizer: picks up Scout's handoff cold, answers with full memory context."""

    def __init__(self, store, llm=None):
        super().__init__("scribe", "Scribe", "summarizer", store, llm)

    def act(self, user_id: str, query: str, trace=None) -> str:
        handoffs = Handoff(self.store)
        handoff = handoffs.latest_for(user_id, self.agent_id)
        extra = ""
        if handoff:
            research = handoffs.shared_state(
                user_id, STATE_KEY, agent_id=self.agent_id
            )
            q_words = set(significant_words(query, limit=12))
            haystack = f"{handoff['summary']} {research or ''}"
            if research and q_words & set(significant_words(haystack, limit=24)):
                extra = (
                    f"Latest handoff from {handoff['from']}: {handoff['summary']}\n"
                    f"Research findings:\n{research}"
                )
                handoffs.mark_consumed(user_id, handoff["id"])
        return self.think(user_id, query, trace=trace, extra_context=extra)
