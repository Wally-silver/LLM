from __future__ import annotations

from typing import TypedDict

from app.services.agent_schema import CriticResult, Plan, PlanStep


class AgentState(TypedDict, total=False):
    task: str
    plan: dict
    current_step: int
    history: list[dict]
    shared: dict
    status: str
    retry_count: int
    max_reflections: int
    replan_count: int
    max_replans: int
    last_error: dict
    completed_steps: list[int]
    skipped_steps: list[int]


class AgentOrchestrator:
    """State-driven orchestrator with retry/replan/skip/fallback branch control."""

    def __init__(self, planner, executor, critic, replanner=None):
        self.planner_fn = planner
        self.executor_fn = executor
        self.critic_fn = critic
        self.replanner_fn = replanner

    @staticmethod
    def _get_step(plan: Plan, step_id: int) -> PlanStep | None:
        return next((s for s in plan.steps if s.id == step_id), None)

    @staticmethod
    def _dependencies_satisfied(step: PlanStep, completed_steps: list[int]) -> bool:
        return all(dep in completed_steps for dep in step.depends_on)

    @staticmethod
    def _next_runnable_step(plan: Plan, completed_steps: list[int], skipped_steps: list[int]) -> PlanStep | None:
        for step in sorted(plan.steps, key=lambda x: x.id):
            if step.id in completed_steps or step.id in skipped_steps:
                continue
            if all(dep in completed_steps for dep in step.depends_on):
                return step
        return None

    @staticmethod
    def _append_history(state: AgentState, step: PlanStep, result: dict, critic: CriticResult, retry_index: int, decision: str):
        item = {
            "step": step.to_dict(),
            "io": result,
            "critic": critic.to_dict(),
            "retry_index": retry_index,
            "transition_decision": decision,
        }
        state["history"].append(item)

    async def run(self, task: str, max_reflections: int = 2, max_replans: int = 1) -> AgentState:
        state: AgentState = {
            "task": task,
            "history": [],
            "shared": {},
            "status": "running",
            "current_step": 1,
            "retry_count": 0,
            "max_reflections": max_reflections,
            "replan_count": 0,
            "max_replans": max_replans,
            "last_error": {},
            "completed_steps": [],
            "skipped_steps": [],
        }

        plan: Plan = await self.planner_fn(task)
        state["plan"] = plan.to_dict()
        if not plan.steps:
            state["status"] = "failed"
            state["last_error"] = {"type": "logic_error", "message": "empty plan"}
            return state

        while state["status"] == "running":
            step = self._next_runnable_step(plan, state["completed_steps"], state["skipped_steps"])
            if step is None:
                # no runnable step: either all done or deadlock
                unresolved = [s for s in plan.steps if s.id not in state["completed_steps"] and s.id not in state["skipped_steps"]]
                state["status"] = "done" if not unresolved else "failed"
                if unresolved:
                    state["last_error"] = {"type": "logic_error", "message": "no runnable step due to dependency deadlock"}
                break

            state["current_step"] = step.id
            if not self._dependencies_satisfied(step, state["completed_steps"]):
                state["status"] = "failed"
                state["last_error"] = {"type": "logic_error", "message": f"dependencies unsatisfied for step {step.id}"}
                break

            result = await self.executor_fn(step=step, state=state)
            critic = await self.critic_fn(step=step, result=result, state=state)

            # transition decisions
            decision = "advance"
            if critic.should_retry and state["retry_count"] < state["max_reflections"]:
                state["retry_count"] += 1
                decision = "retry"
                self._append_history(state, step, result, critic, state["retry_count"], decision)
                continue

            if critic.should_replan and self.replanner_fn and state["replan_count"] < state["max_replans"]:
                state["replan_count"] += 1
                new_plan = await self.replanner_fn(state=state, failed_step=step, critic=critic)
                if new_plan and new_plan.steps:
                    plan = new_plan
                    state["plan"] = plan.to_dict()
                    decision = "replan"
                    self._append_history(state, step, result, critic, state["retry_count"], decision)
                    state["retry_count"] = 0
                    continue

            if critic.should_skip:
                state["skipped_steps"].append(step.id)
                decision = "skip"
                self._append_history(state, step, result, critic, state["retry_count"], decision)
                state["retry_count"] = 0
                continue

            if critic.needs_revision and step.fallback_action:
                fallback_step = PlanStep(
                    id=step.id,
                    action=step.fallback_action,
                    description=f"fallback for step {step.id}",
                    depends_on=step.depends_on,
                    expected_output=step.expected_output,
                )
                fallback_result = await self.executor_fn(step=fallback_step, state=state)
                fallback_critic = await self.critic_fn(step=fallback_step, result=fallback_result, state=state)
                decision = "fallback"
                self._append_history(state, fallback_step, fallback_result, fallback_critic, state["retry_count"], decision)
                if fallback_critic.needs_revision:
                    state["status"] = "failed"
                    state["last_error"] = {"type": fallback_critic.error_type, "message": fallback_critic.feedback}
                    break
                state["completed_steps"].append(step.id)
                state["retry_count"] = 0
                continue

            if critic.needs_revision:
                decision = "fail"
                self._append_history(state, step, result, critic, state["retry_count"], decision)
                state["status"] = "failed"
                state["last_error"] = {"type": critic.error_type, "message": critic.feedback}
                break

            state["completed_steps"].append(step.id)
            self._append_history(state, step, result, critic, state["retry_count"], decision)
            state["retry_count"] = 0

        return state
