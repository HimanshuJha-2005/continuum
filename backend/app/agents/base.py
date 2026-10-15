class Agent:
    def __init__(self, agent_id: str, name: str, role: str, store, llm):
        self.agent_id = agent_id
        self.name = name
        self.role = role
        self.store = store
        self.llm = llm

    def think(self, user_id: str, task: str, context: list):
        raise NotImplementedError

    def act(self, user_id: str, task: str, context: list):
        raise NotImplementedError
