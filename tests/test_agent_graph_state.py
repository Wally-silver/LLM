import asyncio

from app.services.agent_graph import AgentOrchestrator
from app.services.agent_schema import CriticResult, Plan, PlanStep, ToolCall


def test_retry_replan_dependency_fallback_and_statuses():
    calls = {"step1": 0, "planner": 0, "replan": 0}

    async def planner(_task: str):
        calls["planner"] += 1
        return Plan(
            goal="g",
            strategy="s",
            steps=[
                PlanStep(id=1, action="retrieve_data", expected_output="evidence", fallback_action="tool_call"),
                PlanStep(id=2, action="answer", depends_on=[1], expected_output="final answer"),
            ],
        )

    async def executor(step, state):
        if step.id == 1:
            calls["step1"] += 1
            if calls["step1"] == 1:
                return {"input": {}, "output": {"result": "", "confidence": 0.2, "reasoning": "", "evidence": [], "citations": [], "error": "tool broken"}}
            return {"input": {}, "output": {"result": "ctx", "confidence": 0.9, "reasoning": "ok", "evidence": ["e1"], "citations": [], "error": ""}}
        return {"input": {}, "output": {"result": "ans", "confidence": 0.9, "reasoning": "ok", "evidence": ["e1"], "citations": [], "error": ""}}

    async def critic(step, result, state):
        out = result.get("output", {})
        if step.id == 1 and out.get("error") and state.get("retry_count", 0) == 0:
            return CriticResult(needs_revision=True, should_retry=True, error_type="tool_error", feedback="retry")
        if step.id == 1 and out.get("error"):
            return CriticResult(needs_revision=True, should_replan=True, error_type="logic_error", feedback="replan")
        return CriticResult(score=0.9, confidence=0.9, feedback="ok", needs_revision=False)

    async def replanner(state, failed_step, critic):
        _ = (state, failed_step, critic)
        calls["replan"] += 1
        return Plan(goal="g2", strategy="repair", steps=[PlanStep(id=1, action="retrieve_data"), PlanStep(id=2, action="answer", depends_on=[1])])

    orchestrator = AgentOrchestrator(planner, executor, critic, replanner=replanner)

    async def _run():
        s = await orchestrator.run("task", max_reflections=1, max_replans=1)
        assert s["status"] == "done"
        assert 1 in s["completed_steps"] and 2 in s["completed_steps"]
        assert calls["step1"] >= 2  # retry happened

    asyncio.run(_run())
