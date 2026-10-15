# Cypher queries the product depends on

> Day 1 deliverable — every query the running product executes is documented here.
> FalkorDB runs OpenCypher **over the Redis protocol** (`GRAPH.QUERY`); no Bolt/Neo4j syntax.

## Episodic

(started Day 1)

## Semantic

(started Day 1)

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
