from __future__ import annotations

import json
from typing import TypedDict

from langgraph.graph import END, StateGraph

from app.services.prompting import extract_json


class AgentState(TypedDict, total=False):
    query: str
    rewritten_query: str
    selected_tool: str
    tool_result: dict
    context: str
    answer: str


class AgentOrchestrator:
    def __init__(self, tool_selector, tool_executor, retriever, generator, planner_llm=None):
        self.tool_selector = tool_selector
        self.tool_executor = tool_executor
        self.retriever = retriever
        self.generator = generator
        self.planner_llm = planner_llm
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
        if self.planner_llm is None:
            tool = await self.tool_selector(state["query"])
            return {"selected_tool": tool, "rewritten_query": state["query"]}

        prompt = (
            "你是planner。根据用户问题选择工具。"
            "只输出JSON: {\"tool\": string|null, \"rewritten_query\": string}.\n"
            f"用户问题: {state['query']}"
        )
        raw = await self.planner_llm.complete("You are a strict JSON planner.", prompt, stream=False, max_tokens=200)
        parsed = extract_json(raw)
        tool = parsed.get("tool")
        if tool and not isinstance(tool, str):
            tool = None
        rewritten = parsed.get("rewritten_query") or state["query"]
        return {"selected_tool": tool, "rewritten_query": rewritten}

    async def execute_tool(self, state: AgentState):
        if not state.get("selected_tool"):
            return {}
        result = await self.tool_executor(state["selected_tool"], query=state.get("rewritten_query", state["query"]))
        return {"tool_result": result}

    async def retrieve(self, state: AgentState):
        context = await self.retriever(state.get("rewritten_query", state["query"]))
        return {"context": context}

    async def generate(self, state: AgentState):
        answer = await self.generator(state)
        return {"answer": answer}

    async def run(self, query: str) -> AgentState:
        return await self.graph.ainvoke({"query": query})
