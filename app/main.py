"""FastAPI application entrypoint.

该模块负责把各个子系统（RAG / LLM / Agent / Cache / Memory / Metrics）装配到统一 API 层，
并提供 `/ask` 与 `/agent` 两个对外接口。
"""

import json
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse

from app.config import settings
from app.schemas import AgentRequest, AskRequest, StructuredAnswer
from app.services.agent_graph import AgentOrchestrator
from app.services.cache import CacheService
from app.services.llm_client import VLLMOpenAIClient
from app.services.memory import SessionMemory
from app.services.metrics import Metrics
from app.services.prompting import SYSTEM_PROMPT, build_user_prompt, extract_json
from app.services.rag import RAGService
from app.services.tools import Tool, ToolRegistry


@asynccontextmanager
async def lifespan(_: FastAPI):
    """应用生命周期钩子。

    这里保留了启动/关闭扩展点，方便后续接入数据库连接池、监控 exporter 等资源。
    """
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)
memory = SessionMemory()
metrics = Metrics()
cache = CacheService(settings.redis_url, settings.cache_ttl_seconds)
llm = VLLMOpenAIClient(settings.openai_compatible_base_url, settings.openai_api_key, settings.llm_model_name)
rag = RAGService(settings.embedding_model, settings.rerank_model, settings.chunk_token_size, settings.rag_top_k)
tools = ToolRegistry()

# demo corpus：示例知识库，实际生产中可替换为文件系统/对象存储/数据库加载。
rag.build_index(
    [
        ("doc-1", "RAG combines retrieval and generation to reduce hallucination and improve factuality."),
        ("doc-2", "vLLM improves throughput via paged KV cache and continuous batching."),
    ]
)


async def weather_tool(**kwargs):
    """示例工具：天气查询（当前为 mock 数据）。"""
    city = kwargs.get("query", "unknown")
    return {"city": city, "weather": "sunny", "source": "mock"}


async def rag_tool(**kwargs):
    """示例工具：直接调用 RAG 进行检索并返回 chunk 列表。"""
    query = kwargs.get("query", "")
    chunks = rag.retrieve(query)
    return {"chunks": [c.text for c in chunks]}


tools.register(Tool(name="weather", description="Get weather info", handler=weather_tool))
tools.register(Tool(name="rag_search", description="Semantic retrieve internal knowledge", handler=rag_tool))


async def select_tool(query: str) -> str | None:
    """轻量规则 Planner：根据 query 关键词决定是否调用工具。"""
    q = query.lower()
    if "天气" in q or "weather" in q:
        return "weather"
    if any(x in q for x in ["文档", "知识库", "检索", "rag"]):
        return "rag_search"
    return None


async def execute_tool(name: str, **kwargs):
    """工具执行器：统一从注册中心调用工具。"""
    return await tools.call(name, **kwargs)


async def retrieve_context(query: str, top_k: int | None = None):
    """Retriever 节点：从向量库取回上下文并拼接为提示词可用文本。"""
    chunks = rag.retrieve(query, top_k=top_k)
    return "\n".join([f"[{c.doc_id}] {c.text}" for c in chunks])


async def generate_answer(state):
    """Generator 节点：基于 query + context 调用 LLM 生成答案。"""
    user_prompt = build_user_prompt(state["query"], state.get("context", ""), history="")
    return await llm.complete(SYSTEM_PROMPT, user_prompt, stream=False)


agent = AgentOrchestrator(select_tool, execute_tool, retrieve_context, generate_answer)


@app.get("/health")
async def health():
    """健康检查与轻量指标输出。"""
    return {"status": "ok", "metrics": metrics.snapshot()}


@app.post("/ask")
async def ask(req: AskRequest):
    """直接问答接口。

    流程：
    1) 查 Redis 缓存；
    2) 组装会话历史与 RAG 上下文；
    3) 流式/非流式调用 LLM；
    4) 持久化会话记忆与缓存。
    """
    metrics.inc("requests")
    with metrics.track_latency():
        cached = await cache.get(req.session_id, req.query)
        if cached:
            metrics.inc("cache_hits")
            return JSONResponse(cached)

        history = memory.history_as_text(req.session_id)
        context = await retrieve_context(req.query)
        prompt = build_user_prompt(req.query, context, history)

        if req.stream:
            # SSE 流式输出：让前端尽早收到增量 token，降低感知时延。
            async def event_stream():
                stream = await llm.complete(SYSTEM_PROMPT, prompt, stream=True)
                async for chunk in stream:
                    yield f"data: {chunk}\n\n"

            return StreamingResponse(event_stream(), media_type="text/event-stream")

        output = await llm.complete(SYSTEM_PROMPT, prompt, stream=False)
        parsed = extract_json(output)
        result = StructuredAnswer(
            answer=parsed.get("answer", output),
            citations=parsed.get("citations", []),
            used_tools=parsed.get("used_tools", []),
            metadata=parsed.get("metadata", {}),
            latency_ms=metrics.latencies_ms[-1] if metrics.latencies_ms else 0,
            cache_hit=False,
        ).model_dump()

        memory.add_turn(req.session_id, "user", req.query)
        memory.add_turn(req.session_id, "assistant", result["answer"])
        await cache.set(req.session_id, req.query, result)
        return JSONResponse(result)


@app.post("/agent")
async def run_agent(req: AgentRequest):
    """Agent 编排入口：使用 LangGraph 执行 Planner/Tool/Retriever/Generator 流程。"""
    metrics.inc("requests")
    with metrics.track_latency():
        try:
            state = await agent.run(req.query)
            result = {
                "answer": state.get("answer", ""),
                "tool_result": state.get("tool_result"),
                "context": state.get("context", ""),
                "selected_tool": state.get("selected_tool"),
                "latency_ms": metrics.latencies_ms[-1] if metrics.latencies_ms else 0,
            }
            return JSONResponse(result)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Agent execution failed: {exc}") from exc
