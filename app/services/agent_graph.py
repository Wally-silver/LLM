"""LangGraph-based agent orchestration.

节点定义：
- Planner：决定是否调用工具
- Tool Executor：执行工具
- Retriever：调用 RAG
- Generator：调用 LLM 生成最终答案
"""

from typing import TypedDict

from langgraph.graph import END, StateGraph


class AgentState(TypedDict, total=False):
    """Agent 在图执行过程中的共享状态。"""

    query: str
    rewritten_query: str
    selected_tool: str
    tool_result: dict
    context: str
    answer: str


class AgentOrchestrator:
    """封装 StateGraph 的编排器。"""

    def __init__(self, tool_selector, tool_executor, retriever, generator):
        self.tool_selector = tool_selector
        self.tool_executor = tool_executor
        self.retriever = retriever
        self.generator = generator
        self.graph = self._build_graph()

    def _build_graph(self):
        """构建有向状态图。"""
        g = StateGraph(AgentState)
        g.add_node("planner", self.planner)
        g.add_node("tool_executor", self.execute_tool)
        g.add_node("retriever", self.retrieve)
        g.add_node("generator", self.generate)

        g.set_entry_point("planner")
        # Planner 根据意图决定流程分支。
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
        """规划节点：选择工具。"""
        tool = await self.tool_selector(state["query"])
        return {"selected_tool": tool, "rewritten_query": state["query"]}

    async def execute_tool(self, state: AgentState):
        """工具执行节点。"""
        if not state.get("selected_tool"):
            return {}
        result = await self.tool_executor(state["selected_tool"], query=state["query"])
        return {"tool_result": result}

    async def retrieve(self, state: AgentState):
        """检索节点：获取用于生成的上下文。"""
        context = await self.retriever(state["query"])
        return {"context": context}

    async def generate(self, state: AgentState):
        """生成节点：调用 LLM。"""
        answer = await self.generator(state)
        return {"answer": answer}

    async def run(self, query: str) -> AgentState:
        """执行完整图流程。"""
        return await self.graph.ainvoke({"query": query})
