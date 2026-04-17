from __future__ import annotations

from typing import TypedDict

from app.services.agent_schema import CriticResult, Plan


class AgentState(TypedDict, total=False):
    task: str
    plan: dict
    current_step: int
    history: list[dict]
    shared: dict
    status: str
    retry_count: int
    max_reflections: int


class AgentOrchestrator:
    """State-driven orchestrator (planner -> executor -> critic) without hard framework dependency."""

    def __init__(self, planner, executor, critic):
        self.planner_fn = planner
        self.executor_fn = executor
        self.critic_fn = critic

    async def run(self, task: str, max_reflections: int = 2) -> AgentState:
        state: AgentState = {
            "task": task,
            "history": [],
            "shared": {},
            "status": "running",
            "current_step": 1,
            "retry_count": 0,
            "max_reflections": max_reflections,
        }

        plan: Plan = await self.planner_fn(task)
        state["plan"] = plan.to_dict()
        if not plan.steps:
            state["status"] = "failed"
            return state

        while state["status"] == "running":
            current = state["current_step"]
            step = next((s for s in plan.steps if s.id == current), None)
            if step is None:
                state["status"] = "done"
                break

            result = await self.executor_fn(step=step, state=state)
            state["history"].append(
                {
                    "step": {"id": step.id, "action": step.action, "tool_call": {"tool": step.tool_call.tool, "args": step.tool_call.args}},
                    "result": result,
                }
            )
            critic: CriticResult = await self.critic_fn(step=step, result=result, state=state)
            state["history"][-1]["critic"] = critic.to_dict()

            if critic.needs_revision and state["retry_count"] < state["max_reflections"]:
                state["retry_count"] += 1
                continue

            state["retry_count"] = 0
            state["current_step"] += 1
            if state["current_step"] > len(plan.steps):
                state["status"] = "done"

        return state
