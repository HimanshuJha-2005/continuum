from falkordb import FalkorDB

from app.config import settings
from app.schema import ensure_schema


class GraphStore:
    def __init__(self, host: str | None = None, port: int | None = None):
        self.client = FalkorDB(
            host=host or settings.falkordb_host,
            port=port or settings.falkordb_port,
        )
        self._indexed: set[str] = set()

    def user_graph(self, user_id: str):
        graph = self.client.select_graph(f"user:{user_id}")
        if user_id not in self._indexed:
            ensure_schema(graph)
            self._indexed.add(user_id)
        return graph

    def query(self, user_id: str, cypher: str, params: dict | None = None):
        return self.user_graph(user_id).query(cypher, params=params or {})

    def ro_query(self, user_id: str, cypher: str, params: dict | None = None):
        return self.user_graph(user_id).ro_query(cypher, params=params or {})


store = GraphStore()
