# Cypher queries the product depends on

> Day 1 deliverable — every query the running product executes is documented here.
> FalkorDB runs OpenCypher **over the Redis protocol** (`GRAPH.QUERY`); no Bolt/Neo4j syntax.

## Episodic

(started Day 1)

## Semantic

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

## Handoff & shared state

(started Day 2)
