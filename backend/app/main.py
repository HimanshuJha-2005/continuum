import uuid

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.agents.handoff import Handoff
from app.agents.scribe import Scribe
from app.agents.scout import Scout
from app.falkor import store
from app.memory.episodic import EpisodicMemory
from app.memory.procedural import ProceduralMemory
from app.memory.semantic import SemanticMemory
from app.seed import seed as seed_demo
from app.trace import Trace

app = FastAPI(title="Continuum", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    user_id: str
    message: str
    session_id: str = "web"
    agent: str = "scribe"


def _node_label(node) -> str:
    props = node.properties
    labels = set(node.labels or [])
    if "Turn" in labels:
        return str(props.get("content", ""))[:36]
    if "Procedure" in labels:
        return str(props.get("name", ""))[:36]
    if "Fact" in labels:
        subj = props.get("subject", "")
        val = props.get("value", "")
        if subj and val:
            return f"{subj} → {val}"[:44]
    for key in ("name", "key", "subject"):
        if key in props:
            return str(props[key])[:44]
    if "id" in props:
        return str(props["id"])
    if "content" in props:
        return str(props["content"])[:36]
    return str(node.id)


def _elements(result) -> dict:
    nodes: dict[int, dict] = {}
    edges: dict[int, dict] = {}

    def add_node(node) -> None:
        props = dict(node.properties)
        content = props.get("content")
        if isinstance(content, str) and len(content) > 300:
            props["content"] = content[:300] + "…"
        nodes[node.id] = {
            "data": {
                "id": node.id,
                "label": _node_label(node),
                "type": (node.labels or ["?"])[0],
                "props": props,
                "valid_to": props.get("valid_to"),
            }
        }

    for row in result.result_set:
        node, rel, neighbor = row[0], row[1], row[2]
        add_node(node)
        if rel is not None:
            add_node(neighbor)
            edges[rel.id] = {
                "data": {
                    "id": rel.id,
                    "source": rel.src_node.id if hasattr(rel.src_node, "id") else rel.src_node,
                    "target": rel.dest_node.id if hasattr(rel.dest_node, "id") else rel.dest_node,
                    "type": rel.relation,
                }
            }
    return {"nodes": list(nodes.values()), "edges": list(edges.values())}


@app.get("/health")
def health():
    try:
        store.client.select_graph("_health").query("RETURN 1")
        db = "up"
    except Exception as e:
        db = f"down: {e}"
    return {"status": "ok", "falkordb": db}


@app.get("/")
def root():
    return {"name": "Continuum", "status": "ok"}


@app.post("/chat")
def chat(body: ChatRequest):
    epi = EpisodicMemory(store)
    sem = SemanticMemory(store)
    turn_id = epi.add_turn(body.user_id, body.session_id, "user", body.message)
    trace = Trace(turn_id=turn_id)
    try:
        extracted = sem.extract(body.user_id, body.message, turn_id=turn_id)
        extraction = {
            "facts": len(extracted["facts"]),
            "entities": len(extracted["entities"]),
            "preferences": len(extracted.get("preferences", [])),
        }
        if extracted.get("skipped"):
            extraction["skipped"] = True
    except Exception as e:
        extraction = {"error": str(e)[:200]}
    try:
        if body.agent == "scout":
            scout = Scout(store)
            result = scout.act(body.user_id, body.message, trace=trace)
            response = {"findings": result}
        else:
            scribe = Scribe(store)
            answer = scribe.act(body.user_id, body.message, trace=trace)
            epi.add_turn(body.user_id, body.session_id, "assistant", answer)
            response = {"answer": answer}
            if scribe.last_coordinated:
                response["coordinated"] = True
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"agent failed: {e}")
    response["extracted"] = extraction
    response["turn_id"] = turn_id
    response["trace"] = trace.to_dict()
    return response


@app.get("/memory")
def memory_summary(user_id: str):
    epi = EpisodicMemory(store)
    sem = SemanticMemory(store)
    proc = ProceduralMemory(store)
    return {
        "sessions": epi.recent_sessions(user_id, limit=10),
        "facts": sem.recall(user_id, "", limit=50),
        "preferences": proc.preferences(user_id),
        "procedures": proc.procedures(user_id),
        "shared_state": Handoff(store).entries(user_id),
    }


@app.get("/memory/full")
def memory_full(user_id: str):
    result = store.ro_query(
        user_id,
        """
        MATCH (n)
        OPTIONAL MATCH (n)-[r]-(m)
        RETURN n, r, m
        LIMIT 500
        """,
    )
    return {"user_id": user_id, **_elements(result)}


@app.get("/session_turns")
def session_turns(user_id: str, session_id: str):
    turns = EpisodicMemory(store).session_turns(user_id, session_id)
    return {"session_id": session_id, "turns": turns}


@app.get("/memory/subgraph")
def memory_subgraph(user_id: str, node_ids: str = Query(..., description="comma-separated internal node ids")):
    try:
        ids = [int(x) for x in node_ids.split(",") if x.strip()]
    except ValueError:
        raise HTTPException(status_code=400, detail="node_ids must be comma-separated integers")
    if not ids:
        raise HTTPException(status_code=400, detail="no node ids given")
    result = store.ro_query(
        user_id,
        """
        MATCH (n) WHERE id(n) IN $ids
        OPTIONAL MATCH (n)-[r]-(m)
        RETURN n, r, m
        LIMIT 300
        """,
        {"ids": ids},
    )
    return {"user_id": user_id, **_elements(result)}


@app.get("/agents")
def agents(user_id: str):
    result = store.ro_query(
        user_id,
        """
        MATCH (a:Agent)
        RETURN a.id, a.name, a.role
        """,
    )
    return {
        "agents": [
            {"id": r[0], "name": r[1], "role": r[2]} for r in result.result_set
        ],
        "handoffs": Handoff(store).recent_all(user_id),
    }


@app.post("/seed")
def seed():
    """Reset and repopulate the demo users (alice/bob) for a clean demo state."""
    return {"seeded": seed_demo(store)}
