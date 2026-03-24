import json
from typing import Any

import redis.asyncio as redis


class CacheService:
    def __init__(self, redis_url: str, ttl_seconds: int = 3600):
        self.client = redis.from_url(redis_url, encoding="utf-8", decode_responses=True)
        self.ttl_seconds = ttl_seconds

    @staticmethod
    def _key(session_id: str, query: str) -> str:
        return f"agent:{session_id}:{query.strip().lower()}"

    async def get(self, session_id: str, query: str) -> dict[str, Any] | None:
        value = await self.client.get(self._key(session_id, query))
        return json.loads(value) if value else None

    async def set(self, session_id: str, query: str, data: dict[str, Any]) -> None:
        await self.client.set(self._key(session_id, query), json.dumps(data), ex=self.ttl_seconds)
