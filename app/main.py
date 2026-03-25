from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager

import httpx
import redis.asyncio as redis
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

from app.config import settings
from app.schemas import AgentRequest, AskRequest, StructuredAnswer
from app.services.agent_graph import AgentOrchestrator
from app.services.cache import CacheService
from app.services.llm_client import VLLMOpenAIClient
from app.services.memory import SessionMemory
from app.services.metrics import Metrics
from app.services.prompting import SYSTEM_PROMPT, build_user_prompt, extract_json, history_fingerprint
from app.services.rag import RAGService
from app.services.tools import Tool, ToolRegistry


@asynccontextmanager
async def lifespan(app: FastAPI):
    redis_client = redis.from_url(settings.redis_url, encoding="utf-8", decode_responses=True)
    http_client = httpx.AsyncClient(timeout=settings.llm_timeout_seconds)

    memory = SessionMemory(redis_client, ttl_seconds=settings.memory_ttl_seconds)
    cache = CacheService(
        redis_client,
        ttl_seconds=settings.cache_ttl_seconds,
        jitter_seconds=settings.cache_jitter_seconds,
        lock_seconds=settings.cache_lock_seconds,
    )
    metrics = Metrics(redis_client, window_size=settings.metrics_window_size)
    llm = VLLMOpenAIClient(
        settings.openai_compatible_base_url,
        settings.openai_api_key,
        settings.llm_model_name,
        http_client,
        max_retries=settings.llm_max_retries,
    )
    rag = RAGService(
        settings.embedding_model,
        settings.rerank_model,
        chunk_token_size=settings.chunk_token_size,
        chunk_overlap=settings.chunk_overlap,
        top_k=settings.rag_top_k,
    )
    tools = ToolRegistry()

    async def weather_tool(**kwargs):
        city = kwargs.get("query", "unknown")
        return {"city": city, "weather": "sunny", "source": "mock"}

    async def rag_tool(**kwargs):
        query = kwargs.get("query", "")
        chunks = await rag.retrieve(query)
        return {"chunks": [c.text for c in chunks]}

    tools.register(Tool(name="weather", description="Get weather info", handler=weather_tool))
    tools.register(Tool(name="rag_search", description="Semantic retrieve internal knowledge", handler=rag_tool))

    # 初始索引，可通过后台任务热更新
    await rag.build_index(
        [
            ("doc-1", "RAG combines retrieval and generation to reduce hallucination and improve factuality."),
            ("doc-2", "vLLM improves throughput via paged KV cache and continuous batching."),
        ]
    )

    async def select_tool(query: str) -> str | None:
        q = query.lower()
        if "天气" in q or "weather" in q:
            return "weather"
        if any(x in q for x in ["文档", "知识库", "检索", "rag"]):
            return "rag_search"
        return None

    async def execute_tool(name: str, **kwargs):
        return await tools.call(name, **kwargs)

    async def retrieve_context(query: str, top_k: int | None = None):
        chunks = await rag.retrieve(query, top_k=top_k)
        return "\n".join([f"[{c.doc_id}] {c.text}" for c in chunks])

    async def generate_answer(state):
        prompt = build_user_prompt(
            state.get("rewritten_query", state["query"]),
            state.get("context", ""),
            history=state.get("history", ""),
            tool_result=state.get("tool_result"),
        )
        return await llm.complete(
            SYSTEM_PROMPT,
            prompt,
            stream=False,
            max_tokens=settings.llm_default_max_tokens,
            response_format={"type": "json_object"},
        )

    agent = AgentOrchestrator(select_tool, execute_tool, retrieve_context, generate_answer, planner_llm=llm)

    app.state.redis = redis_client
    app.state.http_client = http_client
    app.state.memory = memory
    app.state.cache = cache
    app.state.metrics = metrics
    app.state.llm = llm
    app.state.rag = rag
    app.state.tools = tools
    app.state.agent = agent

    # 可选后台定时任务：示例每小时重建索引（演示热更新能力）
    stop_event = asyncio.Event()

    async def periodic_rebuild():
        while not stop_event.is_set():
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=3600)
            except asyncio.TimeoutError:
                await rag.build_index(
                    [
                        ("doc-1", "RAG combines retrieval and generation to reduce hallucination and improve factuality."),
                        ("doc-2", "vLLM improves throughput via paged KV cache and continuous batching."),
                    ]
                )

    task = asyncio.create_task(periodic_rebuild())
    try:
        yield
    finally:
        stop_event.set()
        task.cancel()
        await redis_client.aclose()
        await http_client.aclose()


app = FastAPI(title=settings.app_name, lifespan=lifespan)


def get_memory(request: Request) -> SessionMemory:
    return request.app.state.memory


def get_cache(request: Request) -> CacheService:
    return request.app.state.cache


def get_metrics(request: Request) -> Metrics:
    return request.app.state.metrics


def get_llm(request: Request) -> VLLMOpenAIClient:
    return request.app.state.llm


def get_rag(request: Request) -> RAGService:
    return request.app.state.rag


def get_agent(request: Request) -> AgentOrchestrator:
    return request.app.state.agent


@app.get("/health")
async def health(metrics: Metrics = Depends(get_metrics)):
    return {"status": "ok", "metrics": await metrics.snapshot()}


@app.post("/rag/rebuild")
async def rebuild_rag(docs: list[tuple[str, str]], rag: RAGService = Depends(get_rag)):
    await rag.build_index(docs)
    return {"ok": True, "docs": len(docs)}


async def _non_stream_answer(req: AskRequest, memory: SessionMemory, cache: CacheService, llm: VLLMOpenAIClient, rag: RAGService):
    history = await memory.history_as_text(req.session_id)
    fp = history_fingerprint(history)

    cached = await cache.get(req.session_id, req.query, fp)
    if cached:
        cached["cache_hit"] = True
        return cached

    lock_acquired = await cache.acquire_lock(req.session_id, req.query, fp)
    try:
        if not lock_acquired:
            # 避免击穿：等待已在计算中的请求写入缓存
            for _ in range(5):
                await asyncio.sleep(0.1)
                cached_retry = await cache.get(req.session_id, req.query, fp)
                if cached_retry:
                    cached_retry["cache_hit"] = True
                    return cached_retry

        chunks = await rag.retrieve(req.query)
        context = "\n".join([f"[{c.doc_id}] {c.text}" for c in chunks])
        prompt = build_user_prompt(req.query, context, history)
        output = await llm.complete(
            SYSTEM_PROMPT,
            prompt,
            stream=False,
            max_tokens=settings.llm_default_max_tokens,
            response_format={"type": "json_object"},
        )
        parsed = extract_json(output)
        result = StructuredAnswer(
            answer=parsed.get("answer", output),
            citations=parsed.get("citations", []),
            used_tools=parsed.get("used_tools", []),
            metadata=parsed.get("metadata", {}),
            latency_ms=0,
            cache_hit=False,
        ).model_dump()

        await memory.add_turn(req.session_id, "user", req.query)
        await memory.add_turn(req.session_id, "assistant", result["answer"])
        await cache.set(req.session_id, req.query, result, fp)
        return result
    finally:
        if lock_acquired:
            await cache.release_lock(req.session_id, req.query, fp)


@app.post("/ask")
async def ask(
    req: AskRequest,
    memory: SessionMemory = Depends(get_memory),
    cache: CacheService = Depends(get_cache),
    llm: VLLMOpenAIClient = Depends(get_llm),
    rag: RAGService = Depends(get_rag),
    metrics: Metrics = Depends(get_metrics),
):
    try:
        async with metrics.track("/ask"):
            if req.stream:
                history = await memory.history_as_text(req.session_id)
                chunks = await rag.retrieve(req.query)
                context = "\n".join([f"[{c.doc_id}] {c.text}" for c in chunks])
                prompt = build_user_prompt(req.query, context, history)

                async def event_stream():
                    stream = await llm.complete(
                        SYSTEM_PROMPT,
                        prompt,
                        stream=True,
                        max_tokens=settings.llm_default_max_tokens,
                    )
                    parts = []
                    async for token in stream:
                        parts.append(token)
                        yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"
                    full_answer = "".join(parts)
                    await memory.add_turn(req.session_id, "user", req.query)
                    await memory.add_turn(req.session_id, "assistant", full_answer)

                return StreamingResponse(event_stream(), media_type="text/event-stream")

            result = await _non_stream_answer(req, memory, cache, llm, rag)
            return JSONResponse(result)
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"code": "ASK_FAILED", "message": str(exc)}) from exc


@app.post("/agent")
async def run_agent(
    req: AgentRequest,
    memory: SessionMemory = Depends(get_memory),
    cache: CacheService = Depends(get_cache),
    agent: AgentOrchestrator = Depends(get_agent),
    metrics: Metrics = Depends(get_metrics),
):
    try:
        async with metrics.track("/agent"):
            history = await memory.history_as_text(req.session_id)
            fp = history_fingerprint(history)
            cached = await cache.get(req.session_id, req.query, fp)
            if cached:
                cached["cache_hit"] = True
                return JSONResponse(cached)

            state = await agent.run(req.query)
            answer = state.get("answer", "")
            parsed = extract_json(answer)
            result = {
                "answer": parsed.get("answer", answer),
                "citations": parsed.get("citations", []),
                "used_tools": parsed.get("used_tools", []),
                "metadata": {
                    **parsed.get("metadata", {}),
                    "selected_tool": state.get("selected_tool"),
                    "tool_result": state.get("tool_result"),
                },
                "cache_hit": False,
            }
            await memory.add_turn(req.session_id, "user", req.query)
            await memory.add_turn(req.session_id, "assistant", result["answer"])
            await cache.set(req.session_id, req.query, result, fp)
            return JSONResponse(result)
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"code": "AGENT_FAILED", "message": str(exc)}) from exc
