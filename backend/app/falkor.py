from falkordb import FalkorDB

from app.config import settings


class GraphStore:
    def __init__(self, host: str | None = None, port: int | None = None):
        self.client = FalkorDB(
            host=host or settings.falkordb_host,
            port=port or settings.falkordb_port,
        )

    def user_graph(self, user_id: str):
        return self.client.select_graph(f"user:{user_id}")

    def query(self, user_id: str, cypher: str, args: dict | None = None):
        return self.user_graph(user_id).query(cypher, args=args or {})

    def ro_query(self, user_id: str, cypher: str, args: dict | None = None):
        return self.user_graph(user_id).ro_query(cypher, args=args or {})


store = GraphStore()
