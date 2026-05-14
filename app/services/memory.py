from __future__ import annotations

import json

import redis.asyncio as redis


class SessionMemory:
    """Redis-backed distributed session memory with TTL."""

    def __init__(self, redis_client: redis.Redis, ttl_seconds: int = 86400, max_turns: int = 40):
        self.client = redis_client
        self.ttl_seconds = ttl_seconds
        self.max_turns = max_turns

    @staticmethod
    def _key(session_id: str) -> str:
        return f"mem:{session_id}"

    async def add_turn(self, session_id: str, role: str, content: str) -> None:
        key = self._key(session_id)
        payload = json.dumps({"role": role, "content": content}, ensure_ascii=False)
        pipe = self.client.pipeline()
        pipe.rpush(key, payload)
        pipe.ltrim(key, -self.max_turns, -1)
        pipe.expire(key, self.ttl_seconds)
        await pipe.execute()

    async def get_history(self, session_id: str) -> list[dict[str, str]]:
        values = await self.client.lrange(self._key(session_id), 0, -1)
        return [json.loads(v) for v in values]

    async def history_as_text(self, session_id: str) -> str:
        turns = await self.get_history(session_id)
        return "\n".join([f"{t['role']}: {t['content']}" for t in turns])
