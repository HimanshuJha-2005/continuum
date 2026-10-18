# Cypher queries the product depends on

> Day 1 deliverable — every query the running product executes is documented here.
> FalkorDB runs OpenCypher **over the Redis protocol** (`GRAPH.QUERY`); no Bolt/Neo4j syntax.

## Schema & indexes

Created idempotently on first graph access (`ensure_schema`):

```cypher
CREATE INDEX ON :User(id)
CREATE INDEX ON :Session(id)
CREATE INDEX ON :Turn(ts)
CREATE INDEX ON :Agent(id)
CREATE INDEX ON :Entity(name)
CREATE INDEX ON :Fact(predicate)
CALL db.idx.fulltext.createNodeIndex('Fact', 'subject', 'predicate', 'value')
```

## Handoff & shared state

Record a cross-agent handoff — created **pending**, so it can be injected
once and never re-injected after consumption:

```cypher
MERGE (a:Agent {id: $from_id})
MERGE (b:Agent {id: $to_id})
CREATE (a)-[:HANDOFF_TO {id: $handoff_id, summary: $summary, status: 'pending', ts: timestamp()}]->(b)
```

Latest *pending* handoff received by an agent:

```cypher
MATCH (src:Agent)-[h:HANDOFF_TO]->(dst:Agent {id: $agent_id})
WHERE h.status = 'pending'
RETURN src.id, h.summary, h.ts, h.id
ORDER BY h.ts DESC
LIMIT 1
```

Mark a handoff consumed after the receiving agent used it:

```cypher
MATCH ()-[h:HANDOFF_TO {id: $handoff_id}]->()
SET h.status = 'consumed', h.consumed_at = timestamp()
```

Write shared state (WROTE edge makes the authorship auditable):

```cypher
MERGE (s:SharedState {user_id: $user_id, key: $key})
SET s.value = $value, s.updated_at = timestamp()
WITH s
MERGE (a:Agent {id: $agent_id})
MERGE (a)-[w:WROTE]->(s)
SET w.ts = timestamp()
```

Read shared state as an agent (READ edge recorded):

```cypher
MATCH (s:SharedState {user_id: $user_id, key: $key})
RETURN s.value
```

```cypher
MATCH (s:SharedState {user_id: $user_id, key: $key})
WITH s
MERGE (a:Agent {id: $agent_id})
MERGE (a)-[r:READ]->(s)
SET r.ts = timestamp()
```

## Episodic

Start (or re-open) a session for a user:

```cypher
MERGE (u:User {id: $user_id})
MERGE (s:Session {id: $session_id})
ON CREATE SET s.started_at = timestamp()
MERGE (u)-[:HAS_SESSION]->(s)
```

Append a turn to a session — self-sufficient (MERGEs the user and session if
missing, so live web chat never silently drops turns):

```cypher
MERGE (u:User {id: $user_id})
MERGE (s:Session {id: $session_id})
ON CREATE SET s.started_at = timestamp()
MERGE (u)-[:HAS_SESSION]->(s)
CREATE (t:Turn {id: $turn_id, role: $role, content: $content, ts: timestamp(), seq: $seq})
CREATE (s)-[:CONTAINS]->(t)
```

List a user's sessions, newest first:

```cypher
MATCH (u:User {id: $user_id})-[:HAS_SESSION]->(s:Session)
RETURN s.id, s.started_at
ORDER BY s.started_at DESC
LIMIT $limit
```

Read a session's turns in order (tiebroken by a nanosecond creation `seq`,
because FalkorDB recycles internal ids after deletes and `id()` can't order
same-millisecond turns):

```cypher
MATCH (u:User {id: $user_id})-[:HAS_SESSION]->(s:Session {id: $session_id})-[:CONTAINS]->(t:Turn)
RETURN t.role, t.content, t.ts
ORDER BY t.ts ASC, t.seq ASC
```

## Agent retrieval

Recent turns for the prompt context (newest first):

```cypher
MATCH (u:User {id: $user_id})-[:HAS_SESSION]->(:Session)-[:CONTAINS]->(t:Turn)
RETURN t
ORDER BY t.ts DESC, t.seq DESC
LIMIT $limit
```

Primary fact lookup — native full-text index over `Fact` (terms joined with
FalkorDB's `|` OR operator, superseded facts excluded):

```cypher
CALL db.idx.fulltext.queryNodes('Fact', $q) YIELD node, score
WHERE node.valid_to IS NULL
RETURN node, score
ORDER BY score DESC
LIMIT $limit
```

Substring keyword match — runs when full-text scores fewer than 3 facts
(catches stems full-text misses: "prefer" vs "preferred"). Words are
stopword-filtered tokens of 2+ chars, so "Go"/"API"/"AWS" match and an
all-stopword question never degenerates into match-everything:

```cypher
MATCH (f:Fact)
WHERE any(w IN $words WHERE toLower(f.subject) CONTAINS w
          OR toLower(f.predicate) CONTAINS w
          OR toLower(f.value) CONTAINS w)
AND f.valid_to IS NULL
RETURN f
ORDER BY f.confidence DESC
LIMIT $limit
```

Temporal history — two paths, selected by the question. Keyword-anchored walk:
anchor on any word-matched fact (active or superseded), then follow
`SUPERSEDES` chains:

```cypher
MATCH (f:Fact)
WHERE any(w IN $words WHERE toLower(f.subject) CONTAINS w
          OR toLower(f.predicate) CONTAINS w
          OR toLower(f.value) CONTAINS w)
OPTIONAL MATCH (newer:Fact)-[:SUPERSEDES*1..5]->(f)
WITH DISTINCT COALESCE(newer, f) AS root
OPTIONAL MATCH path = (root)-[:SUPERSEDES*1..5]->(old:Fact)
RETURN root, [n IN nodes(path) | n.value] AS evolution
LIMIT 6
```

When the question uses temporal wording (`before`, `previously`, `was`,
`history`, …) keyword overlap is unreliable — "what database were we using
before" shares no word with "Continuum uses FastAPI backend…". Those questions
instead walk every chain root directly:

```cypher
MATCH path = (root:Fact)-[:SUPERSEDES*1..5]->(old:Fact)
WHERE NOT (root)<-[:SUPERSEDES]-()
RETURN root, [n IN nodes(path) | n.value] AS evolution
ORDER BY root.last_seen DESC
LIMIT 6
```

Entity context — facts reached through `Turn-[:MENTIONS]->Entity-[:RELATES]->Fact`,
so recall follows the graph instead of only scanning Fact properties:

```cypher
MATCH (u:User {id: $user_id})-[:HAS_SESSION]->(:Session)-[:CONTAINS]->(t:Turn)
MATCH (t)-[:MENTIONS]->(e:Entity)
MATCH (e)-[:RELATES]->(f:Fact)
WHERE f.valid_to IS NULL
RETURN DISTINCT f
ORDER BY f.confidence DESC
LIMIT $limit
```

Fallback when keyword match comes up thin — newest active facts regardless of
keywords (the model judges relevance):

```cypher
MATCH (f:Fact)
WHERE f.valid_to IS NULL
RETURN f
ORDER BY f.last_seen DESC, f.confidence DESC
LIMIT $limit
```

Scout's entity expansion — everything linked to the entities behind matched
facts:

```cypher
MATCH (e:Entity)-[:RELATES]->(f:Fact)
WHERE f.id IN $seed_ids
MATCH (e)-[:RELATES]->(other:Fact)
WHERE other.valid_to IS NULL
RETURN e, other
LIMIT 30
```

Zero-seed fallback — when keyword retrieval found no facts (`matched == 0`),
Scout seeds expansion from entities mentioned in the user's recent turns
instead of skipping:

```cypher
MATCH (u:User {id: $user_id})-[:HAS_SESSION]->(:Session)-[:CONTAINS]->(t:Turn)
MATCH (t)-[:MENTIONS]->(e:Entity)
MATCH (e)-[:RELATES]->(f:Fact)
WHERE f.valid_to IS NULL
RETURN e, f
LIMIT 30
```

Procedures for Scribe's context (so the agent can recite or follow recorded
steps on trigger):

```cypher
MATCH (u:User {id: $user_id})-[:HAS_PROCEDURE]->(p:Procedure)
RETURN p
```

## Semantic

Upsert an entity (type defaults to `concept` when created via fact extraction):

```cypher
MERGE (e:Entity {name: $name})
SET e.type = $type
```

Link an extracted entity back to the turn that mentioned it:

```cypher
MATCH (t:Turn {id: $turn_id})
MATCH (e:Entity {name: $name})
MERGE (t)-[:MENTIONS]->(e)
```

Conflict check before upsert — every *active* fact with the same subject gets
candidate status (invariant: at most one active fact per subject/topic). The
Cypher is deliberately loose (same subject, any predicate, different value);
Python then filters candidates by `_same_topic` — same predicate verbatim, or
same head verb (first verb-ish token, trailing-s stripped, >= 4 chars). This
survives LLM phrasing drift ("uses for"/"uses" both head-verb to "use"):

```cypher
MATCH (f:Fact {subject: $subject})
WHERE f.value <> $value
AND f.valid_to IS NULL
RETURN f.id, f.predicate, f.value
```

Upsert a fact (same subject/predicate/value merges; confidence refreshed,
`last_seen` bumped, a dead fact with that value is reactivated):

```cypher
MERGE (subj:Entity {name: $subject})
MERGE (f:Fact {subject: $subject, predicate: $predicate, value: $value})
ON CREATE SET f.id = $fact_id, f.confidence = $confidence, f.valid_from = timestamp()
ON MATCH SET f.last_seen = timestamp(), f.confidence = $confidence, f.valid_to = NULL
MERGE (subj)-[:RELATES {predicate: $predicate}]->(f)
RETURN f.id
```

Link a fact to the turn it was extracted from:

```cypher
MATCH (t:Turn {id: $turn_id})
MATCH (f:Fact {id: $fact_id})
CREATE (t)-[:DERIVED {ts: timestamp()}]->(f)
```

Keyword recall across active facts (confidence-ordered):

```cypher
MATCH (f:Fact)
WHERE (toLower(f.subject) CONTAINS toLower($q)
    OR toLower(f.predicate) CONTAINS toLower($q)
    OR toLower(f.value) CONTAINS toLower($q))
AND f.valid_to IS NULL
RETURN f
ORDER BY f.confidence DESC
LIMIT $limit
```

Supersede a fact (temporal validity: old gets `valid_to`; the new value
MERGEs so re-stating a previous value reactivates it instead of duplicating):

```cypher
MATCH (old:Fact {id: $old_id})
SET old.valid_to = timestamp()
MERGE (n:Fact {subject: $subject, predicate: $predicate, value: $value})
ON CREATE SET n.id = $new_id, n.confidence = $confidence, n.valid_from = timestamp()
ON MATCH SET n.last_seen = timestamp(), n.confidence = $confidence, n.valid_to = NULL
MERGE (n)-[:SUPERSEDES]->(old)
RETURN n.id
```

Relink the subject entity to the new fact (keeps `RELATES` expansion working
on the current version):

```cypher
MATCH (s:Entity {name: $subject})-[:RELATES]->(:Fact {id: $old_id})
MERGE (s)-[:RELATES {predicate: $predicate}]->(:Fact {id: $stored_id})
```

## Procedural

Record or update a preference (latest value wins via MERGE):

```cypher
MERGE (u:User {id: $user_id})
MERGE (p:Preference {key: $key})
SET p.value = $value, p.updated_at = timestamp()
MERGE (u)-[:PREFERS]->(p)
```

Read all preferences for a user:

```cypher
MATCH (u:User {id: $user_id})-[:PREFERS]->(p:Preference)
RETURN p.key, p.value
```

Record or update a learned procedure:

```cypher
MERGE (u:User {id: $user_id})
MERGE (p:Procedure {name: $name})
SET p.steps = $steps, p.trigger = $trigger, p.updated_at = timestamp()
MERGE (u)-[:HAS_PROCEDURE]->(p)
```

List procedures, optionally filtered by trigger:

```cypher
MATCH (u:User {id: $user_id})-[:HAS_PROCEDURE]->(p:Procedure)
WHERE $trigger IS NULL OR p.trigger = $trigger
RETURN p.name, p.steps, p.trigger
```
