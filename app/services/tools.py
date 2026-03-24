from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any


@dataclass
class Tool:
    name: str
    description: str
    handler: Callable[..., Awaitable[dict[str, Any]]]


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def list_tools(self) -> list[dict[str, str]]:
        return [{"name": t.name, "description": t.description} for t in self._tools.values()]

    async def call(self, name: str, **kwargs) -> dict[str, Any]:
        if name not in self._tools:
            raise ValueError(f"Tool '{name}' not found")
        return await self._tools[name].handler(**kwargs)
