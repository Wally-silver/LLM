import asyncio

from app.services.evaluator import AutoEvaluator


async def _dummy_answer(question: str, context: str) -> str:
    _ = context
    # intentionally simplistic to keep deterministic tests
    return question


def test_evaluator_runs_on_all_datasets():
    evaluator = AutoEvaluator()

    async def _run():
        result = await evaluator.evaluate(answer_func=_dummy_answer, limit_per_dataset=1)
        assert "datasets" in result
        assert len(result["datasets"]) == 7
        assert "overall" in result

    asyncio.run(_run())
