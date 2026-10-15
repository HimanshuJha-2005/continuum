import sys

from falkordb import FalkorDB


def main() -> int:
    client = FalkorDB(host="localhost", port=6379)
    graph = client.select_graph("continuum_verify")

    graph.query("CREATE (u:User {id: 'verify', name: 'Verify'})")
    result = graph.ro_query("MATCH (u:User {id: 'verify'}) RETURN u.name")
    assert result.result_set == [["Verify"]], f"unexpected: {result.result_set}"

    graph.query("MATCH (u:User {id: 'verify'}) DETACH DELETE u")
    print("GRAPH.QUERY round-trip OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
