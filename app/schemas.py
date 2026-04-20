from typing import Any

from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    session_id: str = Field(..., description="Session identifier for memory")
    query: str
    stream: bool = True
    use_rag: bool = True
    show_retrieval: bool = True


class AgentRequest(AskRequest):
    top_k: int | None = None


class StructuredAnswer(BaseModel):
    answer: str
    citations: list[str] = Field(default_factory=list)
    used_tools: list[str] = Field(default_factory=list)
    latency_ms: int
    cache_hit: bool
    metadata: dict[str, Any] = Field(default_factory=dict)


class IngestSourceRequest(BaseModel):
    source_type: str = Field(description="inline | file | url | directory | json | jsonl | csv")
    source_value: str = Field(description="文本内容、文件路径、目录路径或URL")
    doc_id: str | None = Field(default=None, description="可选文档ID")
    recursive: bool = True
    overwrite: bool = True


class SourceInfo(BaseModel):
    doc_id: str
    source_type: str
    source_value: str


class RAGStats(BaseModel):
    document_count: int
    source_count: int
    chunk_count: int
    index_ready: bool
    embedding_model: str
    reranker_model: str
    neo4j_enabled: bool
    neo4j_connected: bool


class RetrievedHit(BaseModel):
    doc_id: str
    title: str | None = None
    source_type: str | None = None
    source_value: str | None = None
    score: float | None = None
    snippet: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class AskResult(BaseModel):
    answer: str
    use_rag: bool
    rag_context: str = ""
    retrieved_docs: list[RetrievedHit] = Field(default_factory=list)
    kg_hits: list[str] = Field(default_factory=list)
    citations: list[str] = Field(default_factory=list)
    used_tools: list[str] = Field(default_factory=list)
    latency_ms: int = 0
    cache_hit: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class CompareResponse(BaseModel):
    query: str
    no_rag_answer: str
    rag_answer: str
    rag_context: str
    retrieved_docs: list[RetrievedHit] = Field(default_factory=list)
    kg_hits: list[str] = Field(default_factory=list)
    no_rag_latency_ms: int
    rag_latency_ms: int
    latency_diff_ms: int
