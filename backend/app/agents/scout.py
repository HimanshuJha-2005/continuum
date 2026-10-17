from app.agents.base import Agent
from app.agents.handoff import Handoff

STATE_KEY = "research"

ENTITY_EXPANSION = """
MATCH (e:Entity)-[:RELATES]->(f:Fact)
WHERE f.id IN $seed_ids
MATCH (e)-[:RELATES]->(other:Fact)
WHERE other.valid_to IS NULL
RETURN e, other
LIMIT 30
"""


class Scout(Agent):
    """Researcher: multi-hop exploration of the graph, publishes a research
    report to shared state, hands off to Scribe."""

    def __init__(self, store, llm=None):
        super().__init__("scout", "Scout", "researcher", store, llm)

    def act(self, user_id: str, query: str, trace=None) -> str:
        ctx = self.build_context(user_id, query, trace)

        seed_ids = [f["id"] for f in ctx["facts"] if f.get("id")]
        related: list[dict] = []
        entities: dict[str, str] = {}
        if seed_ids:
            result = self.store.ro_query(
                user_id, ENTITY_EXPANSION, {"seed_ids": seed_ids}
            )
            if trace:
                trace.add(ENTITY_EXPANSION, {"seed_ids": seed_ids}, result, "semantic")
            for row in result.result_set:
                e_node, f_node = row[0], row[1]
                entities[e_node.properties.get("name", "")] = e_node.properties.get(
                    "type", ""
                )
                related.append(dict(f_node.properties))

        seen_values = {(f.get("subject"), f.get("predicate"), f.get("value")) for f in ctx["facts"]}
        related = [
            f
            for f in related
            if (f.get("subject"), f.get("predicate"), f.get("value")) not in seen_values
        ]

        title = f'Research report for "{query}"'
        lines: list[str] = []
        lines.append(f"Direct facts ({len(ctx['facts'])}):")
        if ctx["facts"]:
            lines += [
                f"- {f.get('subject')} {f.get('predicate')} {f.get('value')}"
                for f in ctx["facts"]
            ]
        else:
            lines.append("- none matched")
        if entities:
            lines.append(f"\nEntities ({len(entities)}):")
            lines += [f"- {n} ({t})" for n, t in list(entities.items())[:8]]
        if related:
            lines.append(f"\nRelated facts via entity links ({len(related)}):")
            lines += [
                f"- {f.get('subject')} {f.get('predicate')} {f.get('value')}"
                for f in related[:8]
            ]
        if ctx["turns"]:
            lines.append(f"\nRecent turns: {len(ctx['turns'])}")
        evidence = "\n".join(lines)

        synthesis = ""
        try:
            synthesis = self.llm.complete(
                f"Research question: {query}\n\n"
                f"Evidence from the memory graph:\n{evidence}\n\n"
                "Write a 3-4 sentence research summary based only on this evidence. "
                "Cite concrete facts as [fact: subject predicate value]. "
                "If the evidence does not answer the question, say what is missing.",
                system=(
                    "You are Scout, a graph research agent. Use only the evidence "
                    "provided — no outside knowledge. Be concrete and direct."
                ),
            ).strip()
        except Exception:
            synthesis = ""
        report = title + (f"\n\n{synthesis}" if synthesis else "") + f"\n\n{evidence}"

        handoffs = Handoff(self.store)
        handoffs.set_shared_state(user_id, STATE_KEY, report, self.agent_id)
        summary = (
            f"Researched '{query}': {len(ctx['facts'])} facts, "
            f"{len(entities)} entities, {len(related)} linked facts"
        )
        handoffs.create(user_id, self.agent_id, "scribe", summary)
        return report
