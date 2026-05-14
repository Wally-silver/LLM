from __future__ import annotations

import hashlib
import json
import random
from typing import Any

import redis.asyncio as redis


class CacheService:
    def __init__(self, redis_client: redis.Redis, ttl_seconds: int = 3600, jitter_seconds: int = 300, lock_seconds: int = 15):
        self.client = redis_client
        self.ttl_seconds = ttl_seconds
        self.jitter_seconds = jitter_seconds
        self.lock_seconds = lock_seconds

    @staticmethod
    def _hash_text(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def _key(self, session_id: str, query: str, history_fingerprint: str = "") -> str:
        digest = self._hash_text(f"{session_id}|{query.strip().lower()}|{history_fingerprint}")
        return f"cache:{digest}"

    def _lock_key(self, key: str) -> str:
        return f"{key}:lock"

    async def get(self, session_id: str, query: str, history_fingerprint: str = "") -> dict[str, Any] | None:
        value = await self.client.get(self._key(session_id, query, history_fingerprint))
        if value is None:
            return None
        data = json.loads(value)
        if data.get("_null"):
            return None
        return data

    async def set(self, session_id: str, query: str, data: dict[str, Any] | None, history_fingerprint: str = "") -> None:
        key = self._key(session_id, query, history_fingerprint)
        ttl = self.ttl_seconds + random.randint(0, max(0, self.jitter_seconds))
        payload = data if data is not None else {"_null": True}
        await self.client.set(key, json.dumps(payload, ensure_ascii=False), ex=ttl)

    async def acquire_lock(self, session_id: str, query: str, history_fingerprint: str = "") -> bool:
        key = self._key(session_id, query, history_fingerprint)
        return bool(await self.client.set(self._lock_key(key), "1", ex=self.lock_seconds, nx=True))

    async def release_lock(self, session_id: str, query: str, history_fingerprint: str = "") -> None:
        key = self._key(session_id, query, history_fingerprint)
        await self.client.delete(self._lock_key(key))
