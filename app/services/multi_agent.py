from __future__ import annotations

from app.services.agent_graph import AgentOrchestrator
from app.services.agent_schema import AgentIO, CriticResult, Plan, PlanStep, ToolCall

import json


def safe_get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return default


def normalize_step_result(result):
    if result is None:
        return ""
    if isinstance(result, str):
        return result.strip()
    if isinstance(result, dict):
        return (
            safe_get(result, "answer")
            or safe_get(result, "result")
            or safe_get(result, "output")
            or json.dumps(result, ensure_ascii=False)
        )
    return str(result)

from app.services.prompting import (
    SYSTEM_PROMPT,
    build_executor_prompt,
    build_planner_prompt,
    build_replanner_prompt,
    extract_json,
)


class MultiAgentCoordinator:
    """Planner / Executor / Critic autonomous coordinator with replan and reflection."""

    def __init__(self, llm, rag, kg, tools, reflection_threshold: float = 0.75, max_reflections: int = 2, max_replans: int = 1):
        self.llm = llm
        self.rag = rag
        self.kg = kg
        self.tools = tools
        self.reflection_threshold = reflection_threshold
        self.max_reflections = max_reflections
        self.max_replans = max_replans

    async def _plan(self, query: str, history: str) -> Plan:
        prompt = build_planner_prompt(query, history)
        raw = await self.llm.complete(
            "You are a strict planner.",
            prompt,
            stream=False,
            response_format={"type": "json_object"},
        )
        parsed = extract_json(raw)
        plan = Plan.from_dict(parsed)
        if plan.steps:
            return plan

        is_recommend = any(k in query.lower() for k in ["推荐", "recommend", "redial"])
        return Plan(
            goal=query,
            strategy="fallback_dynamic",
            steps=[
                PlanStep(
                    id=1,
                    action="retrieve_data",
                    description="collect evidence from rag and kg",
                    expected_output="evidence items",
                    tool_call=ToolCall(tool="rag_search", args={"query": query}, purpose="retrieve knowledge", required=False),
                    fallback_action="tool_call",
                ),
                PlanStep(
                    id=2,
                    action="analyze",
                    description="reason over evidence",
                    depends_on=[1],
                    expected_output="analysis with citations",
                    fallback_action="summarize",
                ),
                PlanStep(
                    id=3,
                    action="answer" if not is_recommend else "summarize",
                    description="final response",
                    depends_on=[2],
                    expected_output="final answer",
                    fallback_action="summarize",
                ),
            ],
        )

    async def _replan(self, query: str, history: str, state: dict, failed_step: PlanStep, critic: CriticResult) -> Plan:
        prompt = build_replanner_prompt(query, state, failed_step.to_dict(), critic.to_dict())
        raw = await self.llm.complete(
            "You are a strict replanner.",
            prompt,
            stream=False,
            response_format={"type": "json_object"},
        )
        parsed = extract_json(raw)
        replanned = Plan.from_dict(parsed)
        if replanned.steps:
            completed = set(state.get("completed_steps", []))
            for step in replanned.steps:
                if step.id in completed:
                    step.status = "completed"
            return replanned

        return Plan(
            goal=query,
            strategy="minimal_replan",
            steps=[
                PlanStep(id=1, action="retrieve_data", description="re-retrieve evidence", expected_output="evidence", fallback_action="tool_call"),
                PlanStep(id=2, action="answer", depends_on=[1], description="answer with available evidence", expected_output="answer"),
            ],
        )

    async def _execute_step(self, step: PlanStep, state: dict) -> AgentIO:
        query = state["task"]
        shared = state.setdefault("shared", {})
        history_text = "\n".join([str(x) for x in state.get("history", [])[-3:]])

        if step.action == "retrieve_data":
            evidence = []
            error = ""
            try:
                if step.tool_call.tool:
                    tool_args = step.tool_call.args or {"query": query}
                    tool_result = await self.tools.call(step.tool_call.tool, **tool_args)
                    shared["tool_result"] = tool_result
                    evidence.append(str(tool_result))
                chunks = await self.rag.retrieve(query)
                evidence.extend([f"[{c.doc_id}] {c.text}" for c in chunks])
                kg_related = await self.kg.search_related(query, limit=5)
                evidence.extend(kg_related)
                shared["evidence"] = evidence
                shared["context"] = "\n".join(evidence)
            except Exception as exc:
                error = str(exc)
            return AgentIO(
                input={"query": query, "step": step.to_dict()},
                output={
                    "result": shared.get("context", ""),
                    "confidence": 0.85 if evidence else 0.2,
                    "reasoning": "retrieval completed" if evidence else "retrieval failed",
                    "evidence": evidence,
                    "citations": [],
                    "error": error,
                },
            )

        if step.action == "tool_call":
            try:
                if not step.tool_call.tool:
                    raise ValueError("tool_error: missing tool name")
                result = await self.tools.call(step.tool_call.tool, **step.tool_call.args)
                shared["tool_result"] = result
                return AgentIO(
                    input={"tool": step.tool_call.tool, "args": step.tool_call.args},
                    output={"result": result, "confidence": 0.8, "reasoning": "tool executed", "evidence": [str(result)], "citations": [], "error": ""},
                )
            except Exception as exc:
                return AgentIO(
                    input={"tool": step.tool_call.tool, "args": step.tool_call.args},
                    output={"result": {}, "confidence": 0.1, "reasoning": "tool failed", "evidence": [], "citations": [], "error": str(exc)},
                )

        prompt = build_executor_prompt(
            action=step.action,
            query=query,
            context=shared.get("context", ""),
            history=history_text,
            tool_result=shared.get("tool_result", {}),
        )
        raw = await self.llm.complete(
            SYSTEM_PROMPT,
            prompt,
            stream=False,
            response_format={"type": "json_object"},
        )
        parsed = extract_json(raw)
        text = parsed.get("answer", raw)
        if step.action in {"summarize", "answer"}:
            shared["answer"] = text
        return AgentIO(
            input={"action": step.action, "expected_output": step.expected_output},
            output={
                "result": text,
                "confidence": 0.75,
                "reasoning": f"llm {step.action}",
                "evidence": shared.get("evidence", []),
                "citations": parsed.get("citations", []),
                "error": "",
            },
        )

    async def _critic(self, step: PlanStep, io: AgentIO, state: dict) -> CriticResult:
        out = io.output if isinstance(io.output, dict) else {}
        has_result = bool(safe_get(out, "result"))
        has_error = bool(safe_get(out, "error"))
        has_evidence = bool(safe_get(out, "evidence"))

        if has_error:
            return CriticResult(
                score=0.2,
                confidence=0.8,
                feedback="tool execution error",
                needs_revision=True,
                error_type="tool_error",
                suggestion="check tool args or switch fallback",
                should_retry=True,
                should_replan=state.get("retry_count", 0) >= state.get("max_reflections", 2),
            )

        if step.action == "retrieve_data" and not has_evidence:
            return CriticResult(
                score=0.3,
                confidence=0.7,
                feedback="missing evidence",
                needs_revision=True,
                error_type="missing_data",
                suggestion="retry retrieval or call alternative tool",
                should_retry=True,
            )

        if step.action in {"analyze", "answer", "summarize"} and not has_evidence:
            return CriticResult(
                score=0.45,
                confidence=0.7,
                feedback="reasoning lacks evidence grounding",
                needs_revision=True,
                error_type="reasoning_error",
                suggestion="retrieve evidence before reasoning",
                should_replan=state.get("retry_count", 0) >= state.get("max_reflections", 2),
                should_retry=state.get("retry_count", 0) < state.get("max_reflections", 2),
            )

        if not has_result:
            return CriticResult(
                score=0.4,
                confidence=0.6,
                feedback="empty result",
                needs_revision=True,
                error_type="logic_error",
                suggestion="skip or fallback",
                should_skip=not step.fallback_action,
            )

        return CriticResult(score=0.9, confidence=0.85, feedback="accepted", needs_revision=False, error_type="none")

    async def run(self, query: str, history: str = "") -> dict:
        async def planner_adapter(task: str):
            return await self._plan(task, history)

        async def executor_adapter(step, state):
            io = await self._execute_step(step, state)
            return io.to_dict()

        async def critic_adapter(step, result, state):
            io = AgentIO.from_dict(result)
            return await self._critic(step, io, state)

        async def replanner_adapter(state, failed_step, critic):
            return await self._replan(query, history, state, failed_step, critic)

        orchestrator = AgentOrchestrator(
            planner=planner_adapter,
            executor=executor_adapter,
            critic=critic_adapter,
            replanner=replanner_adapter,
        )

        final_state = await orchestrator.run(query, max_reflections=self.max_reflections, max_replans=self.max_replans)
        plan = final_state.get("plan", {})
        answer = normalize_step_result(safe_get(safe_get(final_state, "shared", {}), "answer", ""))
        if not answer:
            for h in reversed(safe_get(final_state, "history", []) or []):
                candidates = [
                    safe_get(safe_get(safe_get(h, "io", {}), "output", {}), "result"),
                    safe_get(safe_get(h, "result", {}), "output", {}),
                    safe_get(h, "result"),
                ]
                for c in candidates:
                    text = normalize_step_result(c)
                    if text:
                        answer = text
                        break
                if answer:
                    break
        if not answer:
            answer = "Agent任务已完成，但没有生成有效总结。"
        reflections = sum(1 for h in (final_state.get("history", []) or []) if safe_get(h, "transition_decision") == "retry")
        used_tools = []
        for h in (final_state.get("history", []) or []):
            step = safe_get(h, "step", {})
            tool_call = safe_get(step, "tool_call", {})
            tool = safe_get(tool_call, "tool")
            if tool:
                used_tools.append(tool)

        return {
            "task_type": "autonomous_agent",
            "answer": answer,
            "citations": [],
            "used_tools": used_tools,
            "metadata": {
                "agents": ["planner", "executor", "critic", "replanner"],
                "plan": plan,
                "final_state": final_state,
                "reflection_count": reflections,
                "replan_count": final_state.get("replan_count", 0),
                "completed_steps": final_state.get("completed_steps", []),
                "skipped_steps": final_state.get("skipped_steps", []),
            },
            "context": final_state.get("shared", {}).get("context", ""),
        }
