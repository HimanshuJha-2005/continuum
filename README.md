# Continuum

**Cross-agent graph memory with explainable recall.**
Built for [Graph Hacks: Context for AI Agents](https://www.wemakedevs.org/hackathons/falkordb) (FalkorDB) — Track 02: Agent Memory & Coordination.

An AI assistant that remembers you — and shows you why it remembers. Two agents
(**Scout** finds/extracts, **Scribe** summarizes/acts) share persistent memory
stored as a property graph in FalkorDB:

- **Episodic** — sessions and turns with timestamps
- **Semantic** — facts and entities, extracted and linked
- **Procedural** — preferences and learned procedures

Every user gets an isolated graph inside a single FalkorDB instance
(multigraph topology = one tenant brain per graph). Every answer ships with a
**memory trace**: the exact nodes and edges traversed and the Cypher that
fetched them, rendered live as a subgraph beside the chat.

## Quickstart

```bash
# 1. Start FalkorDB (with persistent volume) + backend
docker compose up --build

# 2. Verify the graph round-trip
python scripts/verify_graph.py

# 3. Frontend (dev)
cd frontend && npm install && npm run dev
```

- FalkorDB Browser: http://localhost:3000
- Backend API: http://localhost:8000/health
- Frontend: http://localhost:5173

Copy `.env.example` to `.env` and add your `GEMINI_API_KEY` (free tier at
https://aistudio.google.com) or `GROQ_API_KEY`.

## Graph model

See [docs/graph-model.md](docs/graph-model.md).

## Cypher queries the product depends on

See [docs/cypher.md](docs/cypher.md).

## License

MIT

Built with AI coding assistance, disclosed per Graph Hacks rules.
