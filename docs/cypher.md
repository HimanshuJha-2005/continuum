# Cypher queries the product depends on

> Day 1 deliverable — every query the running product executes is documented here.
> FalkorDB runs OpenCypher **over the Redis protocol** (`GRAPH.QUERY`); no Bolt/Neo4j syntax.

## Handoff & shared state

Record a cross-agent handoff (`HANDOFF_TO` with summary + timestamp):

```cypher
MERGE (a:Agent {id: $from_id})
MERGE (b:Agent {id: $to_id})
CREATE (a)-[:HANDOFF_TO {id: $handoff_id, summary: $summary, ts: timestamp()}]->(b)
```

Latest handoff received by an agent:

```cypher
MATCH (src:Agent)-[h:HANDOFF_TO]->(dst:Agent {id: $agent_id})
RETURN src.id, h.summary, h.ts, h.id
ORDER BY h.ts DESC
LIMIT 1
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

Append a turn to a session:

```cypher
MATCH (s:Session {id: $session_id})
CREATE (t:Turn {id: $turn_id, role: $role, content: $content, ts: timestamp()})
CREATE (s)-[:CONTAINS]->(t)
```

List a user's sessions, newest first:

```cypher
MATCH (u:User {id: $user_id})-[:HAS_SESSION]->(s:Session)
RETURN s.id, s.started_at
ORDER BY s.started_at DESC
LIMIT $limit
```

Read a session's turns in order (tiebroken by internal id so same-millisecond
turns stay stable):

```cypher
MATCH (u:User {id: $user_id})-[:HAS_SESSION]->(s:Session {id: $session_id})-[:CONTAINS]->(t:Turn)
RETURN t.role, t.content, t.ts
ORDER BY t.ts ASC, id(t) ASC
```

## Agent retrieval

Recent turns for the prompt context (newest first):

```cypher
MATCH (u:User {id: $user_id})-[:HAS_SESSION]->(:Session)-[:CONTAINS]->(t:Turn)
RETURN t
ORDER BY t.ts DESC, id(t) DESC
LIMIT $limit
```

Keyword fact match for the question:

```cypher
MATCH (f:Fact)
WHERE any(w IN $words WHERE toLower(f.subject) CONTAINS w
          OR toLower(f.predicate) CONTAINS w
          OR toLower(f.value) CONTAINS w)
RETURN f
ORDER BY f.confidence DESC
LIMIT $limit
```

Fallback when keyword match comes up thin — newest facts regardless of
keywords (the model judges relevance):

```cypher
MATCH (f:Fact)
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
RETURN e, other
LIMIT 30
```

## Semantic

Conflict check before upsert (same subject + predicate, different value →
supersede instead of parallel fact):

```cypher
MATCH (f:Fact {subject: $subject, predicate: $predicate})
WHERE f.value <> $value
RETURN f.id
LIMIT 1
```

Upsert a fact (same subject/predicate/value merges; confidence refreshed, `last_seen` bumped):

```cypher
MERGE (subj:Entity {name: $subject})
MERGE (f:Fact {subject: $subject, predicate: $predicate, value: $value})
ON CREATE SET f.id = $fact_id, f.confidence = $confidence, f.valid_from = timestamp()
ON MATCH SET f.last_seen = timestamp(), f.confidence = $confidence
MERGE (subj)-[:RELATES {predicate: $predicate}]->(f)
RETURN f.id
```

Link a fact to the turn it was extracted from:

```cypher
MATCH (t:Turn {id: $turn_id})
MATCH (f:Fact {id: $fact_id})
CREATE (t)-[:DERIVED {ts: timestamp()}]->(f)
```

Keyword recall across facts (confidence-ordered):

```cypher
MATCH (f:Fact)
WHERE toLower(f.subject) CONTAINS toLower($q)
   OR toLower(f.predicate) CONTAINS toLower($q)
   OR toLower(f.value) CONTAINS toLower($q)
RETURN f
ORDER BY f.confidence DESC
LIMIT $limit
```

Supersede a fact (temporal validity: old gets `valid_to`, new points at it):

```cypher
MATCH (old:Fact {id: $old_id})
SET old.valid_to = timestamp()
CREATE (n:Fact {id: $new_id, subject: $subject, predicate: $predicate,
                value: $value, confidence: $confidence, valid_from: timestamp()})
CREATE (n)-[:SUPERSEDES]->(old)
WITH n
MATCH (s:Entity {name: $subject})-[:RELATES]->(:Fact {id: $old_id})
MERGE (s)-[:RELATES {predicate: $predicate}]->(n)
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
