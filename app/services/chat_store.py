from __future__ import annotations

import json
from datetime import datetime, timezone


class RedisChatStore:
    def __init__(self, redis_client):
        self.client = redis_client

    @staticmethod
    def _session_key(session_id: str) -> str:
        return f"chat:session:{session_id}"

    @staticmethod
    def _messages_key(session_id: str) -> str:
        return f"chat:messages:{session_id}"

    async def create_session(self, session: dict):
        await self.client.sadd("chat:sessions", session["id"])
        await self.client.set(self._session_key(session["id"]), json.dumps(session, ensure_ascii=False))

    async def list_sessions(self) -> list[dict]:
        ids = await self.client.smembers("chat:sessions")
        out = []
        for sid in ids:
            raw = await self.client.get(self._session_key(sid))
            if raw:
                out.append(json.loads(raw))
        out.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
        return out

    async def get_session(self, session_id: str):
        raw = await self.client.get(self._session_key(session_id))
        if not raw:
            return None
        s = json.loads(raw)
        msgs = await self.client.lrange(self._messages_key(session_id), 0, -1)
        s["messages"] = [json.loads(m) for m in msgs]
        return s

    async def update_session(self, session_id: str, updates: dict):
        cur = await self.get_session(session_id)
        if not cur:
            return None
        cur.update(updates)
        await self.client.set(self._session_key(session_id), json.dumps({k: v for k, v in cur.items() if k != "messages"}, ensure_ascii=False))
        return cur

    async def delete_session(self, session_id: str):
        await self.client.srem("chat:sessions", session_id)
        await self.client.delete(self._session_key(session_id))
        await self.client.delete(self._messages_key(session_id))

    async def add_message(self, session_id: str, message: dict):
        await self.client.rpush(self._messages_key(session_id), json.dumps(message, ensure_ascii=False))
        cur = await self.get_session(session_id)
        if cur:
            cur["updated_at"] = datetime.now(timezone.utc).isoformat()
            cur["message_count"] = len(cur.get("messages", []))
            await self.client.set(self._session_key(session_id), json.dumps({k: v for k, v in cur.items() if k != "messages"}, ensure_ascii=False))


class InMemoryChatStore:
    def __init__(self):
        self.sessions: dict[str, dict] = {}
        self.messages: dict[str, list[dict]] = {}

    async def create_session(self, session: dict):
        self.sessions[session["id"]] = session
        self.messages.setdefault(session["id"], [])

    async def list_sessions(self) -> list[dict]:
        return sorted(self.sessions.values(), key=lambda x: x.get("updated_at", ""), reverse=True)

    async def get_session(self, session_id: str):
        s = self.sessions.get(session_id)
        if not s:
            return None
        return {**s, "messages": list(self.messages.get(session_id, []))}

    async def update_session(self, session_id: str, updates: dict):
        s = self.sessions.get(session_id)
        if not s:
            return None
        s.update(updates)
        return s

    async def delete_session(self, session_id: str):
        self.sessions.pop(session_id, None)
        self.messages.pop(session_id, None)

    async def add_message(self, session_id: str, message: dict):
        self.messages.setdefault(session_id, []).append(message)
        s = self.sessions.get(session_id)
        if s:
            s["updated_at"] = datetime.now(timezone.utc).isoformat()
            s["message_count"] = len(self.messages.get(session_id, []))
