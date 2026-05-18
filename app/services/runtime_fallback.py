from __future__ import annotations

import asyncio
import hashlib
import json
import time
from collections import defaultdict


class InMemorySessionMemory:
    def __init__(self, ttl_seconds: int = 86400, max_turns: int = 40):
        self.ttl_seconds = ttl_seconds
        self.max_turns = max_turns
        self._mem: dict[str, list[dict[str, str]]] = defaultdict(list)
        self._ts: dict[str, float] = {}

    async def add_turn(self, session_id: str, role: str, content: str) -> None:
        now = time.time()
        self._ts[session_id] = now
        self._mem[session_id].append({"role": role, "content": content})
        self._mem[session_id] = self._mem[session_id][-self.max_turns :]

    async def get_history(self, session_id: str) -> list[dict[str, str]]:
        ts = self._ts.get(session_id)
        if ts and (time.time() - ts > self.ttl_seconds):
            self._mem.pop(session_id, None)
            self._ts.pop(session_id, None)
            return []
        return list(self._mem.get(session_id, []))

    async def history_as_text(self, session_id: str) -> str:
        turns = await self.get_history(session_id)
        return "\n".join([f"{t['role']}: {t['content']}" for t in turns])


class InMemoryCacheService:
    def __init__(self, ttl_seconds: int = 3600, lock_seconds: int = 15):
        self.ttl_seconds = ttl_seconds
        self.lock_seconds = lock_seconds
        self._store: dict[str, tuple[float, str]] = {}
        self._locks: dict[str, float] = {}

    @staticmethod
    def _hash_text(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def _key(self, session_id: str, query: str, history_fingerprint: str = "") -> str:
        digest = self._hash_text(f"{session_id}|{query.strip().lower()}|{history_fingerprint}")
        return f"cache:{digest}"

    async def get(self, session_id: str, query: str, history_fingerprint: str = "") -> dict | None:
        key = self._key(session_id, query, history_fingerprint)
        if key not in self._store:
            return None
        expire_at, payload = self._store[key]
        if time.time() > expire_at:
            self._store.pop(key, None)
            return None
        data = json.loads(payload)
        return None if data.get("_null") else data

    async def set(self, session_id: str, query: str, data: dict | None, history_fingerprint: str = "") -> None:
        key = self._key(session_id, query, history_fingerprint)
        payload = data if data is not None else {"_null": True}
        self._store[key] = (time.time() + self.ttl_seconds, json.dumps(payload, ensure_ascii=False))

    async def acquire_lock(self, session_id: str, query: str, history_fingerprint: str = "") -> bool:
        key = self._key(session_id, query, history_fingerprint)
        now = time.time()
        lock_expire = self._locks.get(key, 0)
        if lock_expire > now:
            return False
        self._locks[key] = now + self.lock_seconds
        return True

    async def release_lock(self, session_id: str, query: str, history_fingerprint: str = "") -> None:
        key = self._key(session_id, query, history_fingerprint)
        self._locks.pop(key, None)

