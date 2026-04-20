from __future__ import annotations

from importlib.util import find_spec


class KnowledgeGraphService:
    """Neo4j-backed lightweight knowledge graph service."""

    def __init__(self, uri: str, username: str, password: str, database: str = "neo4j"):
        self.uri = uri
        self.username = username
        self.password = password
        self.database = database
        self.driver = None
        self.last_error: str | None = None

    @property
    def enabled(self) -> bool:
        return bool(self.uri and self.password)

    async def connect(self) -> None:
        if not self.enabled:
            return
        if find_spec("neo4j") is None:
            self.last_error = "neo4j package not installed"
            return
        from neo4j import AsyncGraphDatabase

        try:
            self.driver = AsyncGraphDatabase.driver(self.uri, auth=(self.username, self.password))
            async with self.driver.session(database=self.database) as session:
                await session.run("RETURN 1 AS ok")
            self.last_error = None
        except Exception as exc:
            self.driver = None
            self.last_error = str(exc)

    async def close(self) -> None:
        if self.driver is not None:
            await self.driver.close()

    async def upsert_document(self, doc_id: str, source_type: str, source_value: str, text: str) -> None:
        if self.driver is None:
            return
        preview = text[:500]
        query = (
            "MERGE (d:Document {id: $doc_id}) "
            "SET d.source_type = $source_type, d.source_value = $source_value, d.preview = $preview"
        )
        async with self.driver.session(database=self.database) as session:
            await session.run(
                query,
                doc_id=doc_id,
                source_type=source_type,
                source_value=source_value,
                preview=preview,
            )

    async def search_related(self, keyword: str, limit: int = 3) -> list[str]:
        if self.driver is None:
            return []
        query = (
            "MATCH (d:Document) "
            "WHERE toLower(d.preview) CONTAINS toLower($keyword) OR toLower(d.id) CONTAINS toLower($keyword) "
            "RETURN d.id AS id, d.preview AS preview LIMIT $limit"
        )
        async with self.driver.session(database=self.database) as session:
            result = await session.run(query, keyword=keyword, limit=limit)
            rows = await result.data()
        return [f"[{r['id']}] {r.get('preview','')}" for r in rows]

    def status(self) -> dict:
        return {
            "enabled": self.enabled,
            "connected": self.driver is not None,
            "error": self.last_error,
            "uri": self.uri if self.enabled else "",
            "database": self.database,
        }
