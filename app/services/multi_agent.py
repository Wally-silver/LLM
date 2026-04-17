from __future__ import annotations

from app.services.agent_schema import AgentIO, CriticResult, Plan, PlanStep, ToolCall
from app.services.prompting import SYSTEM_PROMPT, build_user_prompt, extract_json


class MultiAgentCoordinator:
    """Planner / Executor / Critic closed-loop multi-agent system."""

    def __init__(self, llm, rag, kg, tools, reflection_threshold: float = 0.75, max_reflections: int = 2):
        self.llm = llm
        self.rag = rag
        self.kg = kg
        self.tools = tools
        self.reflection_threshold = reflection_threshold
        self.max_reflections = max_reflections

    async def _plan(self, query: str, history: str) -> Plan:
        prompt = (
            "你是Planner。请把任务拆解为结构化计划。\n"
            "输出JSON: {steps:[{id:int, action:str, tool_call:{tool:str|null,args:object}}]}\n"
            "action 仅可用: retrieve_data, tool_call, analyze, summarize, answer.\n"
            f"query={query}\n history={history[-1500:]}"
        )
        raw = await self.llm.complete(
            "You are a strict planner.",
            prompt,
            stream=False,
            response_format={"type": "json_object"},
        )
        parsed = extract_json(raw)
        try:
            plan = Plan.from_dict(parsed)
            if plan.steps:
                return plan
        except Exception:
            pass
        return Plan(
            steps=[
                PlanStep(id=1, action="retrieve_data", tool_call=ToolCall(tool="rag_search", args={"query": query})),
                PlanStep(id=2, action="analyze"),
                PlanStep(id=3, action="answer"),
            ]
        )

    async def _execute_step(self, step: PlanStep, query: str, history: str, shared: dict) -> AgentIO:
        if step.action == "retrieve_data":
            chunks = await self.rag.retrieve(query)
            kg_related = await self.kg.search_related(query, limit=5)
            context = "\n".join([f"[{c.doc_id}] {c.text}" for c in chunks] + kg_related)
            shared["context"] = context
            return AgentIO(
                input={"query": query},
                output={"result": context[:6000], "confidence": 0.8, "reasoning": "retrieved from rag+kg"},
            )

        if step.action == "tool_call" and step.tool_call.tool:
            available = {t["name"] for t in self.tools.list_tools()}
            if step.tool_call.tool not in available:
                return AgentIO(
                    input={"tool": step.tool_call.tool},
                    output={"result": {}, "confidence": 0.1, "reasoning": "tool not found"},
                )
            result = await self.tools.call(step.tool_call.tool, **step.tool_call.args)
            shared["tool_result"] = result
            return AgentIO(
                input={"tool": step.tool_call.tool, "args": step.tool_call.args},
                output={"result": result, "confidence": 0.8, "reasoning": "tool executed"},
            )

        # analyze / summarize / answer
        prompt = build_user_prompt(
            query=query,
            context=shared.get("context", ""),
            history=history,
            tool_result=shared.get("tool_result", {}),
        )
        raw = await self.llm.complete(
            SYSTEM_PROMPT,
            f"[action]={step.action}\n{prompt}",
            stream=False,
            response_format={"type": "json_object"},
        )
        parsed = extract_json(raw)
        text = parsed.get("answer", raw)
        if step.action in {"summarize", "answer"}:
            shared["answer"] = text
        return AgentIO(
            input={"action": step.action},
            output={"result": text, "confidence": 0.75, "reasoning": f"llm {step.action}"},
        )

    async def _critic(self, query: str, step: PlanStep, io: AgentIO, shared: dict) -> CriticResult:
        # 可替换为更强LLM critic；这里保持可控 + 可复现
        result_text = str(io.output.get("result", ""))
        score = 0.9 if result_text else 0.2
        if step.action in {"analyze", "summarize", "answer"} and not shared.get("context"):
            score = 0.5
        needs_revision = score < self.reflection_threshold
        feedback = "insufficient evidence" if needs_revision else "accepted"
        return CriticResult(score=score, confidence=score, feedback=feedback, needs_revision=needs_revision)

    async def run(self, query: str, history: str = "") -> dict:
        state = {
            "task": query,
            "current_step": 0,
            "history": [],
            "shared": {},
            "status": "running",
        }

        plan = await self._plan(query, history)
        if not plan.steps:
            state["status"] = "failed"
            return {
                "task_type": "general",
                "answer": "Planner did not produce a valid plan.",
                "citations": [],
                "used_tools": [],
                "metadata": {"state": state, "plan": plan.to_dict()},
                "context": "",
            }

        for step in plan.steps:
            state["current_step"] = step.id
            reflection_count = 0
            while True:
                io = await self._execute_step(step, query, history, state["shared"])
                critic = await self._critic(query, step, io, state["shared"])
                state["history"].append(
                    {
                        "step": {"id": step.id, "action": step.action, "tool_call": {"tool": step.tool_call.tool, "args": step.tool_call.args}},
                        "io": io.to_dict(),
                        "critic": critic.to_dict(),
                    }
                )
                if not critic.needs_revision or reflection_count >= self.max_reflections:
                    break
                reflection_count += 1

        state["status"] = "completed"
        final_answer = state["shared"].get("answer", "")
        return {
            "task_type": plan.steps[0].action if plan.steps else "general",
            "answer": final_answer,
            "citations": [],
            "used_tools": [h["step"]["tool_call"]["tool"] for h in state["history"] if h["step"]["tool_call"]["tool"]],
            "metadata": {
                "agents": ["planner", "executor", "critic"],
                "plan": plan.to_dict(),
                "state": state,
            },
            "context": state["shared"].get("context", ""),
        }
