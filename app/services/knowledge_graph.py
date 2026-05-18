from __future__ import annotations

import re
from importlib.util import find_spec


class KnowledgeGraphService:
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
            await self.test_connection()
            self.last_error = None
        except Exception as exc:
            self.driver = None
            self.last_error = str(exc)

    async def test_connection(self) -> bool:
        if self.driver is None:
            return False
        try:
            async with self.driver.session(database=self.database) as session:
                await session.run("RETURN 1 AS ok")
            return True
        except Exception as exc:
            self.last_error = str(exc)
            return False

    async def close(self) -> None:
        if self.driver is not None:
            await self.driver.close()


    async def upsert_document(self, doc_id: str, source_type: str, source_value: str, text: str) -> None:
        if self.driver is None:
            return
        preview = (text or "")[:500]
        query = "MERGE (d:Document {id: $doc_id}) SET d.source_type=$source_type, d.source_value=$source_value, d.preview=$preview"
        async with self.driver.session(database=self.database) as session:
            await session.run(query, doc_id=doc_id, source_type=source_type, source_value=source_value, preview=preview)

    async def get_schema_summary(self) -> dict:
        if self.driver is None:
            return {"labels": [], "rel_types": [], "sample_props": {}}
        labels = await self.run_readonly_cypher("MATCH (n) RETURN DISTINCT labels(n) AS labels LIMIT 50")
        rels = await self.run_readonly_cypher("MATCH ()-[r]->() RETURN DISTINCT type(r) AS rel LIMIT 50")
        return {"labels": labels, "rel_types": rels, "sample_props": {}}

    async def search_entities(self, query: str, limit: int = 10) -> list[dict]:
        cypher = "MATCH (n) WHERE any(k in keys(n) WHERE toLower(toString(n[k])) CONTAINS toLower($q)) RETURN n LIMIT $limit"
        rows = await self.run_readonly_cypher(cypher, {"q": query, "limit": limit})
        out = []
        for r in rows:
            n = r.get("n", {}) if isinstance(r, dict) else {}
            out.append({"type": "entity", "nodes": [n], "relationships": [], "text": str(n), "score": None, "source": "neo4j"})
        return out

    async def search_related(self, query: str, limit: int = 10) -> list[dict]:
        cypher = (
            "MATCH (a)-[r]->(b) "
            "WHERE any(k in keys(a) WHERE toLower(toString(a[k])) CONTAINS toLower($q)) "
            "   OR any(k in keys(b) WHERE toLower(toString(b[k])) CONTAINS toLower($q)) "
            "RETURN a, r, b LIMIT $limit"
        )
        rows = await self.run_readonly_cypher(cypher, {"q": query, "limit": limit})
        out = []
        for r in rows:
            a = r.get("a", {}) if isinstance(r, dict) else {}
            b = r.get("b", {}) if isinstance(r, dict) else {}
            rel = r.get("r", {}) if isinstance(r, dict) else {}
            out.append({"type": "relation", "nodes": [a, b], "relationships": [rel], "text": f"{a} -[{rel}]-> {b}", "score": None, "source": "neo4j"})
        return out

    async def find_paths(self, source: str, target: str, max_depth: int = 3) -> list[dict]:
        cypher = (
            f"MATCH p=(a)-[*1..{max(1,min(5,max_depth))}]-(b) "
            "WHERE any(k in keys(a) WHERE toLower(toString(a[k])) CONTAINS toLower($source)) "
            "AND any(k in keys(b) WHERE toLower(toString(b[k])) CONTAINS toLower($target)) "
            "RETURN p LIMIT 10"
        )
        rows = await self.run_readonly_cypher(cypher, {"source": source, "target": target})
        return [{"type": "path", "nodes": [], "relationships": [], "text": str(r.get("p")), "score": None, "source": "neo4j"} for r in rows if isinstance(r, dict)]

    async def run_readonly_cypher(self, cypher: str, params: dict | None = None) -> list[dict]:
        if self.driver is None:
            return []
        c = (cypher or "").strip()
        blocked = ["create", "merge", "delete", "set ", "remove", "call dbms", "load csv"]
        low = c.lower()
        if any(x in low for x in blocked):
            raise ValueError("readonly_cypher_violation")
        if not re.match(r"^(match|with|return)\b", low):
            raise ValueError("readonly_cypher_violation")
        async with self.driver.session(database=self.database) as session:
            result = await session.run(c, **(params or {}))
            return await result.data()

    def status(self) -> dict:
        return {"enabled": self.enabled, "connected": self.driver is not None, "error": self.last_error, "uri": self.uri if self.enabled else "", "database": self.database}
