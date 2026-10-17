from app.agents.base import Agent, significant_words
from app.agents.handoff import Handoff
from app.agents.scout import STATE_KEY, Scout
from app.memory.semantic import QUESTION_RE


class Scribe(Agent):
    """Summarizer: picks up Scout's handoff cold, answers with full memory
    context, and autonomously consults Scout when retrieval comes up thin."""

    def __init__(self, store, llm=None):
        super().__init__("scribe", "Scribe", "summarizer", store, llm)
        self.last_coordinated = False

    def _pickup(self, user_id: str, query: str) -> str:
        handoffs = Handoff(self.store)
        handoffs.expire_stale(user_id)
        handoff = handoffs.latest_for(user_id, self.agent_id)
        if not handoff:
            return ""
        research = handoffs.shared_state(
            user_id, STATE_KEY, agent_id=self.agent_id
        )
        q_words = set(significant_words(query, limit=12))
        haystack = f"{handoff['summary']} {research or ''}"
        if research and q_words & set(significant_words(haystack, limit=24)):
            handoffs.mark_consumed(user_id, handoff["id"])
            return (
                f"Latest handoff from {handoff['from']}: {handoff['summary']}\n"
                f"Research findings:\n{research}"
            )
        return ""

    def act(self, user_id: str, query: str, trace=None) -> str:
        self.last_coordinated = False
        extra = self._pickup(user_id, query)
        if not extra:
            ctx = self.build_context(user_id, query, trace)
            words = significant_words(query)
            if words and ctx.get("matched", 0) == 0 and QUESTION_RE.match(query):
                try:
                    Scout(self.store, llm=self.llm).act(user_id, query, trace=trace)
                    extra = self._pickup(user_id, query)
                    if extra:
                        self.last_coordinated = True
                except Exception:
                    pass
            return self.think(
                user_id, query, trace=trace, extra_context=extra, ctx=ctx
            )
        return self.think(user_id, query, trace=trace, extra_context=extra)
