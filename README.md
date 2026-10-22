# Continuum

Cross-agent memory with traceable recall. Two agents share persistent memory in a property graph, and every answer shows the nodes, edges, and Cypher query it was built from.

Built for Graph Hacks 2026 (FalkorDB track).

## Overview

A user talks to an assistant. Facts, preferences, procedures, and session history are written to FalkorDB as a graph. Two agents work against that graph:

- **Scout** researches a question and writes a handoff.
- **Scribe** answers, pulls relevant memory, and can consult Scout when the memory does not cover the question.

Each user gets a separate graph. Retrieval uses full-text search and multi-hop traversal rather than vector embeddings, so the reasoning path is reproducible and can be displayed next to the answer.

| Memory | Nodes | Purpose |
|---|---|---|
| Episodic | `Session`, `Turn` | What happened, and when |
| Semantic | `Entity`, `Fact` | What is true, with temporal validity |
| Procedural | `Preference`, `Procedure` | How the user wants things done |
| Coordination | `SharedState`, `HANDOFF_TO` | What agents tell each other |

Facts are versioned with `SUPERSEDES` edges. Changing a preference keeps the old value in the graph but removes it from current retrieval, so the history stays available.

## Stack

- Backend: Python, FastAPI, FalkorDB
- Agents: Gemini or Groq for extraction and answering; Scout/Scribe loop in application code
- Frontend: React, cytoscape.js
- Deployment: Docker Compose; nginx serves the frontend and proxies the API

## Quick start

Requirements: Docker Desktop, Python 3.10+, Node 18+.

```bash
pip install -r backend/requirements.txt
cp .env.example .env        # add GEMINI_API_KEY or GROQ_API_KEY
docker compose up --build
python scripts/verify_graph.py
cd frontend && npm install && npm run dev
```

| Service | URL |
|---|---|
| Frontend | http://localhost:5173 |
| API health | http://localhost:8000/health |
| FalkorDB browser | http://localhost:3000 |

## What to try

1. Ask "I prefer TypeScript for new projects." The trace panel shows the episodic, semantic, and procedural steps and their Cypher.
2. Ask "Update: TypeScript is preferred for mobile apps now." The previous fact gains a `SUPERSEDES` edge and leaves current retrieval.
3. Ask "What did I prefer before TypeScript?" A variable-length `SUPERSEDES` walk reconstructs the chain.
4. Switch to Scout, ask a research question, then switch back to Scribe and ask what was decided. Scribe consumes the pending handoff.
5. Ask Scribe something the memory cannot answer. It consults Scout in the same turn; a statement or a known question does not trigger research.

## API

| Method | Route | Purpose |
|---|---|---|
| POST | `/chat` | Ask Scribe or Scout; returns the answer and memory trace |
| GET | `/memory?user_id=` | Sessions, facts, preferences, procedures, shared state |
| GET | `/memory/full?user_id=` | Full graph as cytoscape elements (capped) |
| GET | `/memory/subgraph?user_id=&node_ids=` | Traced nodes and neighbors |
| GET | `/session_turns?user_id=&session_id=` | One session in order |
| GET | `/agents?user_id=` | Agents and handoff history |
| GET | `/health` | Backend and FalkorDB status |

## Testing

Eight suites cover the memory layers, the agent loop, handoffs, cross-user isolation, restart persistence, and an in-process API test. FalkorDB must be running.

```bash
for t in episodic procedural semantic agent handoff scout_scribe api restart; do
  python scripts/test_$t.py
done
```

`test_restart` restarts the FalkorDB container and checks that the graph survives. It also re-seeds the demo users, so run the suites before seeding a demo.

## Performance

Measured with `scripts/bench_concurrent.py`: turn writes, preference writes, and fact/turn/preference reads across 50 tenant graphs, 32 threads, local Docker FalkorDB, steady state.

| Metric | Value |
|---|---|
| Throughput | ~4,300 ops/s |
| Reads p50 / p95 | ~3 ms / ~7 ms |
| Writes p50 / p95 | ~6 ms / ~12 ms |

Cold graphs pay an index build cost on first write (p95 around 90 ms) before settling. Per-user graphs keep query planning isolated between tenants.

## Deployment

`docker-compose.prod.yml` runs FalkorDB, the API, and an nginx container that serves the built frontend and proxies `/chat`, `/memory`, `/agents`, `/health`, `/seed`, and `/session_turns`. The frontend is built in a multi-stage Docker image, so the host does not need Node.

```bash
docker compose -f docker-compose.prod.yml up -d --build
curl -X POST http://<host>/seed
```

Demo: http://16.4.24.249 (AWS EC2, ap-south-1). Video: https://youtu.be/BvvvxxhEayw

## AI assistance

I wrote the backend, graph schema, Cypher queries, agent loop, and test suite. The frontend was built with AI assistance and refined until it matched the product behavior. Benchmark numbers come from the script in this repository. This disclosure follows the Graph Hacks AI-usage rules.

## License

MIT. See [LICENSE](LICENSE).
