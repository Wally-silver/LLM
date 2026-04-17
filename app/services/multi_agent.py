from __future__ import annotations

from app.services.prompting import SYSTEM_PROMPT, build_user_prompt, extract_json


class MultiAgentCoordinator:
    """Task-oriented multi-agent collaboration coordinator."""

    def __init__(self, llm, rag, kg, tools):
        self.llm = llm
        self.rag = rag
        self.kg = kg
        self.tools = tools

    async def _task_router(self, query: str) -> str:
        # 先用规则，后续可切换 LLM 分类器
        q = query.lower()
        if any(k in q for k in ["多跳", "multi-hop", "hotpot", "musique", "2wiki"]):
            return "multi_hop_qa"
        if any(k in q for k in ["多轮", "dialogue", "multiwoz"]):
            return "multi_turn_dialogue"
        if any(k in q for k in ["推荐", "recommend", "redial"]):
            return "personalized_recommendation"
        if any(k in q for k in ["多模态", "scienceqa", "docvqa", "图像", "文档问答"]):
            return "multimodal_reasoning"
        return "general"

    async def _retriever_agent(self, query: str) -> str:
        chunks = await self.rag.retrieve(query)
        return "\n".join([f"[{c.doc_id}] {c.text}" for c in chunks])

    async def _kg_agent(self, query: str) -> str:
        related = await self.kg.search_related(query, limit=5)
        return "\n".join(related)

    async def _tool_agent(self, query: str) -> dict:
        # 简化版：仅根据关键词调用已注册工具
        q = query.lower()
        if "weather" in q or "天气" in q:
            return await self.tools.call("weather", query=query)
        if any(k in q for k in ["检索", "rag", "知识库"]):
            return await self.tools.call("rag_search", query=query)
        return {}

    async def _reasoning_agent(self, query: str, history: str, context: str, tool_result: dict, task_type: str) -> str:
        user_prompt = (
            f"[任务类型]\n{task_type}\n\n"
            + build_user_prompt(query=query, context=context, history=history, tool_result=tool_result)
            + "\n\n请输出可验证结论，必要时说明证据不足。"
        )
        return await self.llm.complete(
            SYSTEM_PROMPT,
            user_prompt,
            stream=False,
            response_format={"type": "json_object"},
        )

    async def _critic_agent(self, query: str, draft_answer: str, context: str) -> str:
        critic_prompt = (
            "你是质量审查Agent。检查答案是否与上下文一致，若不一致请修正。"
            "输出JSON：{answer,citations,used_tools,metadata}.\n"
            f"问题:{query}\n上下文:{context[:4000]}\n草稿:{draft_answer}"
        )
        return await self.llm.complete(
            "You are a strict reviewer.",
            critic_prompt,
            stream=False,
            response_format={"type": "json_object"},
        )

    async def run(self, query: str, history: str = "") -> dict:
        task_type = await self._task_router(query)
        rag_context = await self._retriever_agent(query)
        kg_context = await self._kg_agent(query)
        tool_result = await self._tool_agent(query)
        merged_context = "\n".join([x for x in [rag_context, kg_context] if x])

        draft = await self._reasoning_agent(query, history, merged_context, tool_result, task_type)
        final = await self._critic_agent(query, draft, merged_context)
        parsed = extract_json(final)

        return {
            "task_type": task_type,
            "answer": parsed.get("answer", final),
            "citations": parsed.get("citations", []),
            "used_tools": parsed.get("used_tools", []),
            "metadata": {
                **parsed.get("metadata", {}),
                "agents": ["task_router", "retriever_agent", "kg_agent", "tool_agent", "reasoning_agent", "critic_agent"],
                "tool_result": tool_result,
            },
            "context": merged_context,
        }
