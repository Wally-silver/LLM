from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any


@dataclass
class Tool:
    name: str
    description: str
    handler: Callable[..., Awaitable[dict[str, Any]]]
    input_schema: dict[str, Any] | None = None
    output_schema: dict[str, Any] | None = None


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def list_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "name": t.name,
                "description": t.description,
                "input_schema": t.input_schema,
                "output_schema": t.output_schema,
            }
            for t in self._tools.values()
        ]

    def _validate_input(self, tool: Tool, kwargs: dict[str, Any]) -> None:
        if not tool.input_schema:
            return
        required = tool.input_schema.get("required", [])
        missing = [k for k in required if k not in kwargs]
        if missing:
            raise ValueError(f"tool_error: missing required args {missing} for tool '{tool.name}'")

    async def call(self, name: str, **kwargs) -> dict[str, Any]:
        if name not in self._tools:
            raise ValueError(f"tool_error: tool '{name}' not found")
        tool = self._tools[name]
        self._validate_input(tool, kwargs)
        try:
            result = await tool.handler(**kwargs)
            if tool.output_schema and not isinstance(result, dict):
                raise ValueError(f"tool_error: tool '{name}' output must be dict")
            return result
        except Exception as exc:
            raise RuntimeError(f"tool_error: execution failed for '{name}': {exc}") from exc
