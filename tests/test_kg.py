import asyncio

from app.services.knowledge_graph import KnowledgeGraphService


def test_kg_disabled_mode_no_crash():
    kg = KnowledgeGraphService(uri="", username="neo4j", password="")

    async def _run():
        await kg.connect()
        await kg.upsert_document("d1", "inline", "x", "hello")
        rows = await kg.search_related("hello")
        assert rows == []

    asyncio.run(_run())
