import asyncio

from app.services.multi_agent import MultiAgentCoordinator


class DummyLLM:
    async def complete(self, system_prompt, user_prompt, stream=False, response_format=None, max_tokens=1024):
        _ = (system_prompt, user_prompt, stream, response_format, max_tokens)
        return '{"answer":"ok","citations":[],"used_tools":[],"metadata":{}}'


class DummyRAG:
    async def retrieve(self, query, top_k=None):
        _ = (query, top_k)
        return []


class DummyKG:
    async def search_related(self, keyword, limit=3):
        _ = (keyword, limit)
        return []


class DummyTools:
    async def call(self, name, **kwargs):
        _ = (name, kwargs)
        return {}


def test_multi_agent_run():
    coord = MultiAgentCoordinator(llm=DummyLLM(), rag=DummyRAG(), kg=DummyKG(), tools=DummyTools())

    async def _run():
        result = await coord.run("请做多跳推理")
        assert result["task_type"] in {"retrieve_data", "multi_hop_qa", "general"}
        assert result["answer"] == "ok"
        assert "agents" in result["metadata"]

    asyncio.run(_run())
