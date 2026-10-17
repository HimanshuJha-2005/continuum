INDEX_QUERIES = [
    "CREATE INDEX ON :User(id)",
    "CREATE INDEX ON :Session(id)",
    "CREATE INDEX ON :Turn(ts)",
    "CREATE INDEX ON :Agent(id)",
    "CREATE INDEX ON :Entity(name)",
    "CREATE INDEX ON :Fact(predicate)",
    "CALL db.idx.fulltext.createNodeIndex('Fact', 'subject', 'predicate', 'value')",
]


def ensure_schema(graph) -> None:
    for q in INDEX_QUERIES:
        try:
            graph.query(q)
        except Exception:
            pass
