# Graph model

> Day 1 deliverable — filled as the schema lands.

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
| `HANDOFF_TO` | Agent → Agent | `summary`, `ts` | cross-agent handoff |
| `SUPERSEDES` | Fact → Fact | | temporal validity chain |
| `PREFERS` | User → Preference | | preference ownership |
| `HAS_PROCEDURE` | User → Procedure | | procedure ownership |

## Why this design

(rationale — Day 1)
