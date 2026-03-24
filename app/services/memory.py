from collections import defaultdict, deque


class SessionMemory:
    """Session-level memory, pluggable to Redis in future."""

    def __init__(self, max_turns: int = 20):
        self._store: dict[str, deque[dict[str, str]]] = defaultdict(lambda: deque(maxlen=max_turns))

    def add_turn(self, session_id: str, role: str, content: str) -> None:
        self._store[session_id].append({"role": role, "content": content})

    def get_history(self, session_id: str) -> list[dict[str, str]]:
        return list(self._store[session_id])

    def history_as_text(self, session_id: str) -> str:
        turns = self.get_history(session_id)
        return "\n".join([f"{t['role']}: {t['content']}" for t in turns])
