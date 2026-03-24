from typing import TypedDict

from langgraph.graph import END, StateGraph


class AgentState(TypedDict, total=False):
    query: str
    rewritten_query: str
    selected_tool: str
    tool_result: dict
    context: str
    answer: str


class AgentOrchestrator:
    def __init__(self, tool_selector, tool_executor, retriever, generator):
        self.tool_selector = tool_selector
        self.tool_executor = tool_executor
        self.retriever = retriever
        self.generator = generator
        self.graph = self._build_graph()

    def _build_graph(self):
        g = StateGraph(AgentState)
        g.add_node("planner", self.planner)
        g.add_node("tool_executor", self.execute_tool)
        g.add_node("retriever", self.retrieve)
        g.add_node("generator", self.generate)

        g.set_entry_point("planner")
        g.add_conditional_edges(
            "planner",
            lambda s: "tool_executor" if s.get("selected_tool") else "retriever",
            {"tool_executor": "tool_executor", "retriever": "retriever"},
        )
        g.add_edge("tool_executor", "retriever")
        g.add_edge("retriever", "generator")
        g.add_edge("generator", END)
        return g.compile()

    async def planner(self, state: AgentState):
        tool = await self.tool_selector(state["query"])
        return {"selected_tool": tool, "rewritten_query": state["query"]}

    async def execute_tool(self, state: AgentState):
        if not state.get("selected_tool"):
            return {}
        result = await self.tool_executor(state["selected_tool"], query=state["query"])
        return {"tool_result": result}

    async def retrieve(self, state: AgentState):
        context = await self.retriever(state["query"])
        return {"context": context}

    async def generate(self, state: AgentState):
        answer = await self.generator(state)
        return {"answer": answer}

    async def run(self, query: str) -> AgentState:
        return await self.graph.ainvoke({"query": query})
