from typing import Any

from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    session_id: str = Field(..., description="Session identifier for memory")
    query: str
    stream: bool = True


class AgentRequest(AskRequest):
    top_k: int | None = None


class StructuredAnswer(BaseModel):
    answer: str
    citations: list[str] = Field(default_factory=list)
    used_tools: list[str] = Field(default_factory=list)
    latency_ms: int
    cache_hit: bool
    metadata: dict[str, Any] = Field(default_factory=dict)
