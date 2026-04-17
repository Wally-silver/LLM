import asyncio

from app.services.agent_graph import AgentOrchestrator
from app.services.agent_schema import CriticResult, Plan, PlanStep


async def planner(_task: str):
    return Plan(steps=[PlanStep(id=1, action="analyze"), PlanStep(id=2, action="answer")])


async def executor(step, state):
    return {"result": f"done-{step.id}", "confidence": 0.8, "reasoning": "ok"}


async def critic(step, result, state):
    _ = (step, result, state)
    return CriticResult(score=0.9, confidence=0.9, feedback="ok", needs_revision=False)


def test_state_machine_progress():
    orchestrator = AgentOrchestrator(planner, executor, critic)

    async def _run():
        state = await orchestrator.run("test")
        assert state["status"] == "done"
        assert len(state["history"]) == 2

    asyncio.run(_run())
