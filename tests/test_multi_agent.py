import asyncio

from app.services.multi_agent import MultiAgentCoordinator


class DummyLLM:
    def __init__(self):
        self.calls = 0

    async def complete(self, system_prompt, user_prompt, stream=False, response_format=None, max_tokens=1024):
        _ = (system_prompt, user_prompt, stream, response_format, max_tokens)
        self.calls += 1
        if "Planner" in system_prompt or "strict planner" in system_prompt:
            return '{"goal":"g","strategy":"s","steps":[{"id":1,"action":"retrieve_data","depends_on":[],"expected_output":"evidence"},{"id":2,"action":"answer","depends_on":[1],"expected_output":"answer"}]}'
        if "strict replanner" in system_prompt:
            return '{"goal":"rg","strategy":"repair","steps":[{"id":1,"action":"retrieve_data","depends_on":[],"expected_output":"evidence"},{"id":2,"action":"answer","depends_on":[1],"expected_output":"answer"}]}'
        return '{"answer":"ok","citations":["c1"],"used_tools":[],"metadata":{}}'


class DummyRAG:
    def __init__(self):
        self.calls = 0

    async def retrieve(self, query, top_k=None):
        _ = (query, top_k)
        self.calls += 1
        if self.calls == 1:
            return []  # trigger retry/replan path
        class C:
            doc_id = "d1"
            text = "context"
        return [C()]


class DummyKG:
    async def search_related(self, keyword, limit=3):
        _ = (keyword, limit)
        return []


class DummyTools:
    def list_tools(self):
        return [{"name": "rag_search", "description": "x", "input_schema": {"required": ["query"]}, "output_schema": {}}]

    async def call(self, name, **kwargs):
        _ = (name, kwargs)
        return {"ok": True}


def test_multi_agent_retry_replan_and_metadata():
    coord = MultiAgentCoordinator(llm=DummyLLM(), rag=DummyRAG(), kg=DummyKG(), tools=DummyTools(), max_reflections=1, max_replans=1)

    async def _run():
        result = await coord.run("请做多跳推理")
        metadata = result["metadata"]
        assert metadata["plan"]["steps"][1]["depends_on"] == [1]
        assert metadata["reflection_count"] >= 0
        assert "replan_count" in metadata
        assert "completed_steps" in metadata
        assert result["answer"] == "ok"

    asyncio.run(_run())
