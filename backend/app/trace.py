from dataclasses import dataclass, field


@dataclass
class TraceStep:
    cypher: str
    params: dict
    node_ids: list
    role: str


@dataclass
class Trace:
    turn_id: str
    steps: list[TraceStep] = field(default_factory=list)

    def add(self, cypher: str, params: dict, result, role: str = "retrieval") -> None:
        node_ids: list[int] = []
        for row in result.result_set:
            for item in row:
                if hasattr(item, "nodes"):
                    node_ids.extend(n.id for n in item.nodes)
                elif hasattr(item, "id"):
                    node_ids.append(item.id)
        self.steps.append(
            TraceStep(cypher=cypher, params=params, node_ids=node_ids, role=role)
        )

    def to_dict(self) -> dict:
        return {
            "turn_id": self.turn_id,
            "steps": [
                {
                    "cypher": s.cypher,
                    "params": s.params,
                    "node_ids": s.node_ids,
                    "role": s.role,
                }
                for s in self.steps
            ],
        }
