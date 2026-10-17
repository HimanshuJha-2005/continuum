# Graph model

## Overview

One FalkorDB instance, one graph per user (`user:{id}`) via multigraph topology.

## Node labels

| Label | Key properties | Meaning |
|---|---|---|
| `User` | `id` | Tenant root — owns everything in their graph |
| `Session` | `id`, `started_at` | Episodic: one conversation session |
| `Turn` | `role`, `content`, `ts` | Episodic: a single message within a session |
| `Agent` | `id`, `name` | Scout / Scribe |
| `Entity` | `name`, `type` | Semantic: extracted entities |
| `Fact` | `predicate`, `value`, `confidence`, `valid_from`, `valid_to` | Semantic: extracted facts (temporal) |
| `Procedure` | `name`, `steps`, `trigger` | Procedural: learned how-tos |
| `Preference` | `key`, `value`, `updated_at` | Procedural: user preferences (latest wins) |
| `SharedState` | `key`, `value`, `updated_at` | Handoff scratchpad between agents |

## Relationships

| Edge | From → To | Properties | Meaning |
|---|---|---|---|
| `HAS_SESSION` | User → Session | | tenant ownership |
| `CONTAINS` | Session → Turn | | session membership |
| `MENTIONS` | Turn → Entity | `ts` | entity appeared in a turn |
| `DERIVED` | Turn → Fact | `confidence`, `ts` | fact extracted from a turn |
| `RELATES` | Fact → Entity/Fact | `predicate` | semantic links |
| `WROTE` | Agent → Fact/SharedState | `ts` | authorship |
| `READ` | Agent → Fact/SharedState | `ts` | read provenance |
| `HANDOFF_TO` | Agent → Agent | `summary`, `status` (`pending`/`consumed`), `ts`, `consumed_at` | cross-agent handoff |
| `SUPERSEDES` | Fact → Fact | | temporal validity chain |
| `PREFERS` | User → Preference | | preference ownership |
| `HAS_PROCEDURE` | User → Procedure | | procedure ownership |

## Why this design

- **One graph per user** — Track 02 requires separate memory per tenant.
  FalkorDB's multigraph topology gives every user an isolated brain inside a
  single instance; deleting a tenant is dropping one graph.
- **Turns with timestamps** — episodic recall is meaningless without order.
  `Turn.ts` + `Session.started_at` make "what did we discuss last time" a
  sorted traversal, not a full scan.
- **Temporal facts** — memory must update over time. Facts carry
  `valid_from`/`valid_to`, and a corrected fact `SUPERSEDES` the old one
  instead of overwriting it, so the trace can show how knowledge evolved.
  A variable-length `SUPERSEDES*1..5` walk reconstructs the full chain for
  "what did we use before X" questions.
- **`DERIVED` from Turn to Fact** — every extracted fact points back to the
  message it came from. Explainability starts with provenance.
- **Coordination lives in the graph** — `SharedState` with `WROTE`/`READ`
  edges and `HANDOFF_TO` between agents means the handoff protocol is itself
  traversable data. Remove FalkorDB and the agents cannot coordinate at all.
