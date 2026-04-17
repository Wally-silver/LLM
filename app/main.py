from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager

import httpx
import redis.asyncio as redis
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

from app.config import settings
from app.schemas import AgentRequest, AskRequest, IngestSourceRequest, SourceInfo, StructuredAnswer
from app.services.agent_graph import AgentOrchestrator
from app.services.cache import CacheService
from app.services.llm_client import VLLMOpenAIClient
from app.services.memory import SessionMemory
from app.services.metrics import Metrics
from app.services.prompting import SYSTEM_PROMPT, build_user_prompt, extract_json, history_fingerprint
from app.services.rag import RAGService
from app.services.tools import Tool, ToolRegistry
from app.services.datasource import DataSourceService
from app.services.knowledge_graph import KnowledgeGraphService
from app.services.evaluator import AutoEvaluator, AgentQualityEvaluator
from app.services.multi_agent import MultiAgentCoordinator
from app.domain.windows_it_admin import WINDOWS_IT_ADMIN_SOURCES, WINDOWS_IT_ADMIN_TASKS
from app.domain.advanced_reasoning import (
    ADVANCED_REASONING_DATASET_CATALOG,
    ADVANCED_REASONING_SOURCES,
    ADVANCED_REASONING_TASKS,
)


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
        provider=settings.llm_provider,
    )
    rag = RAGService(
        settings.embedding_model,
        settings.rerank_model,
        chunk_token_size=settings.chunk_token_size,
        chunk_overlap=settings.chunk_overlap,
        top_k=settings.rag_top_k,
    )
    datasource = DataSourceService(http_client, max_chars=settings.datasource_max_chars)
    kg = KnowledgeGraphService(settings.neo4j_uri, settings.neo4j_username, settings.neo4j_password, settings.neo4j_database)
    await kg.connect()
    evaluator = AutoEvaluator()
    agent_quality_evaluator = AgentQualityEvaluator()
    tools = ToolRegistry()
    docs_store: dict[str, dict] = {}

    async def weather_tool(**kwargs):
        city = kwargs.get("query", "unknown")
        return {"city": city, "weather": "sunny", "source": "mock"}

    async def rag_tool(**kwargs):
        query = kwargs.get("query", "")
        chunks = await rag.retrieve(query)
        return {"chunks": [c.text for c in chunks]}

    tools.register(
        Tool(
            name="weather",
            description="Get weather info",
            handler=weather_tool,
            input_schema={"required": ["query"]},
            output_schema={"type": "object"},
        )
    )
    tools.register(
        Tool(
            name="rag_search",
            description="Semantic retrieve internal knowledge",
            handler=rag_tool,
            input_schema={"required": ["query"]},
            output_schema={"type": "object"},
        )
    )

    # 初始数据源示例，可通过 /datasources/ingest 动态注入并热更新索引
    docs_store["doc-1"] = {
        "text": "RAG combines retrieval and generation to reduce hallucination and improve factuality.",
        "source_type": "inline",
        "source_value": "bootstrap",
    }
    docs_store["doc-2"] = {
        "text": "vLLM improves throughput via paged KV cache and continuous batching.",
        "source_type": "inline",
        "source_value": "bootstrap",
    }
    await rag.build_index([(k, v["text"]) for k, v in docs_store.items()])

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

    multi_agent = MultiAgentCoordinator(llm=llm, rag=rag, kg=kg, tools=tools)

    async def graph_planner(task: str):
        return await multi_agent._plan(task, history="")

    async def graph_executor(step, state):
        io = await multi_agent._execute_step(step=step, state=state)
        return io.to_dict()

    async def graph_critic(step, result, state):
        from app.services.agent_schema import AgentIO

        io = AgentIO.from_dict(result)
        return await multi_agent._critic(step, io, state)

    async def graph_replanner(state, failed_step, critic):
        return await multi_agent._replan(state["task"], "", state, failed_step, critic)

    agent = AgentOrchestrator(graph_planner, graph_executor, graph_critic, replanner=graph_replanner)

    app.state.redis = redis_client
    app.state.http_client = http_client
    app.state.memory = memory
    app.state.cache = cache
    app.state.metrics = metrics
    app.state.llm = llm
    app.state.rag = rag
    app.state.datasource = datasource
    app.state.kg = kg
    app.state.evaluator = evaluator
    app.state.agent_quality_evaluator = agent_quality_evaluator
    app.state.docs_store = docs_store
    app.state.tools = tools
    app.state.agent = agent
    app.state.multi_agent = multi_agent

    # 可选后台定时任务：示例每小时重建索引（演示热更新能力）
    stop_event = asyncio.Event()

    async def periodic_rebuild():
        while not stop_event.is_set():
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=3600)
            except asyncio.TimeoutError:
                await rag.build_index([(k, v["text"]) for k, v in docs_store.items()])

    task = asyncio.create_task(periodic_rebuild())
    try:
        yield
    finally:
        stop_event.set()
        task.cancel()
        await kg.close()
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


def get_datasource(request: Request) -> DataSourceService:
    return request.app.state.datasource


def get_docs_store(request: Request) -> dict:
    return request.app.state.docs_store


def get_kg(request: Request) -> KnowledgeGraphService:
    return request.app.state.kg


def get_evaluator(request: Request) -> AutoEvaluator:
    return request.app.state.evaluator


def get_agent_quality_evaluator(request: Request) -> AgentQualityEvaluator:
    return request.app.state.agent_quality_evaluator


def get_multi_agent(request: Request) -> MultiAgentCoordinator:
    return request.app.state.multi_agent


@app.get("/health")
async def health(metrics: Metrics = Depends(get_metrics)):
    return {"status": "ok", "metrics": await metrics.snapshot()}


@app.post("/rag/rebuild")
async def rebuild_rag(docs: list[tuple[str, str]], rag: RAGService = Depends(get_rag)):
    await rag.build_index(docs)
    return {"ok": True, "docs": len(docs)}


@app.get("/datasources", response_model=list[SourceInfo])
async def list_datasources(docs_store: dict = Depends(get_docs_store)):
    return [
        SourceInfo(doc_id=doc_id, source_type=v["source_type"], source_value=v["source_value"])
        for doc_id, v in docs_store.items()
    ]


@app.post("/datasources/bootstrap/windows-it-admin")
async def bootstrap_windows_it_admin(
    datasource: DataSourceService = Depends(get_datasource),
    docs_store: dict = Depends(get_docs_store),
    rag: RAGService = Depends(get_rag),
    kg: KnowledgeGraphService = Depends(get_kg),
):
    loaded = []
    for item in WINDOWS_IT_ADMIN_SOURCES:
        doc = await datasource.load(item["source_type"], item["source_value"], doc_id=item["doc_id"])
        docs_store[doc.doc_id] = {
            "text": doc.text,
            "source_type": doc.source_type,
            "source_value": doc.source_value,
            "task_tags": item.get("task_tags", []),
        }
        loaded.append(doc.doc_id)
        await kg.upsert_document(doc.doc_id, doc.source_type, doc.source_value, doc.text)
    await rag.build_index([(k, v["text"]) for k, v in docs_store.items()])
    return {"ok": True, "loaded_docs": loaded, "tasks": WINDOWS_IT_ADMIN_TASKS}


@app.get("/tasks/windows-it-admin")
async def windows_it_admin_tasks():
    return {"domain": "windows-it-admin", "tasks": WINDOWS_IT_ADMIN_TASKS}


@app.post("/datasources/bootstrap/advanced-reasoning")
async def bootstrap_advanced_reasoning(
    datasource: DataSourceService = Depends(get_datasource),
    docs_store: dict = Depends(get_docs_store),
    rag: RAGService = Depends(get_rag),
    kg: KnowledgeGraphService = Depends(get_kg),
):
    loaded = []
    for item in ADVANCED_REASONING_SOURCES:
        doc = await datasource.load(item["source_type"], item["source_value"], doc_id=item["doc_id"])
        docs_store[doc.doc_id] = {
            "text": doc.text,
            "source_type": doc.source_type,
            "source_value": doc.source_value,
            "task_tags": item.get("task_tags", []),
        }
        loaded.append(doc.doc_id)
        await kg.upsert_document(doc.doc_id, doc.source_type, doc.source_value, doc.text)
    await rag.build_index([(k, v["text"]) for k, v in docs_store.items()])
    return {"ok": True, "loaded_docs": loaded, "tasks": ADVANCED_REASONING_TASKS}


@app.get("/tasks/advanced-reasoning")
async def advanced_reasoning_tasks():
    return {"domain": "advanced-reasoning", "tasks": ADVANCED_REASONING_TASKS}


@app.get("/datasets/catalog")
async def datasets_catalog():
    return {"datasets": ADVANCED_REASONING_DATASET_CATALOG}




@app.get("/eval/datasets")
async def eval_datasets():
    from app.eval.registry import dataset_summaries

    return {"datasets": dataset_summaries()}


@app.post("/eval/run")
async def run_eval(
    limit_per_dataset: int | None = None,
    llm: VLLMOpenAIClient = Depends(get_llm),
    evaluator: AutoEvaluator = Depends(get_evaluator),
):
    async def answer_func(question: str, context: str) -> str:
        prompt = build_user_prompt(question, context, history="")
        output = await llm.complete(
            SYSTEM_PROMPT,
            prompt,
            stream=False,
            max_tokens=settings.llm_default_max_tokens,
            response_format={"type": "json_object"},
        )
        parsed = extract_json(output)
        return parsed.get("answer", output)

    limit = limit_per_dataset or settings.eval_default_limit_per_dataset
    return await evaluator.evaluate(answer_func=answer_func, limit_per_dataset=limit)




@app.post("/eval/agent-quality")
async def eval_agent_quality(
    req: AgentRequest,
    multi_agent: MultiAgentCoordinator = Depends(get_multi_agent),
    evaluator: AgentQualityEvaluator = Depends(get_agent_quality_evaluator),
):
    run_output = await multi_agent.run(req.query, history="")
    return evaluator.evaluate_agent_run(run_output)


@app.post("/datasources/ingest")
async def ingest_datasource(
    req: IngestSourceRequest,
    datasource: DataSourceService = Depends(get_datasource),
    docs_store: dict = Depends(get_docs_store),
    rag: RAGService = Depends(get_rag),
    kg: KnowledgeGraphService = Depends(get_kg),
):
    doc = await datasource.load(req.source_type, req.source_value, doc_id=req.doc_id)
    docs_store[doc.doc_id] = {
        "text": doc.text,
        "source_type": doc.source_type,
        "source_value": doc.source_value,
    }
    await rag.build_index([(k, v["text"]) for k, v in docs_store.items()])
    await kg.upsert_document(doc.doc_id, doc.source_type, doc.source_value, doc.text)
    return {"ok": True, "doc_id": doc.doc_id, "total_docs": len(docs_store)}


async def _non_stream_answer(req: AskRequest, memory: SessionMemory, cache: CacheService, llm: VLLMOpenAIClient, rag: RAGService, kg: KnowledgeGraphService):
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
        kg_related = await kg.search_related(req.query, limit=3)
        context = "\n".join([f"[{c.doc_id}] {c.text}" for c in chunks] + kg_related)
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
    kg: KnowledgeGraphService = Depends(get_kg),
    metrics: Metrics = Depends(get_metrics),
):
    try:
        async with metrics.track("/ask"):
            if req.stream:
                history = await memory.history_as_text(req.session_id)
                chunks = await rag.retrieve(req.query)
                kg_related = await kg.search_related(req.query, limit=3)
                context = "\n".join([f"[{c.doc_id}] {c.text}" for c in chunks] + kg_related)
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

            result = await _non_stream_answer(req, memory, cache, llm, rag, kg)
            return JSONResponse(result)
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"code": "ASK_FAILED", "message": str(exc)}) from exc




@app.get("/agent/capabilities")
async def agent_capabilities():
    return {
        "architecture": "multi_agent",
        "agents": [
            "task_router",
            "retriever_agent",
            "kg_agent",
            "tool_agent",
            "reasoning_agent",
            "critic_agent",
        ],
    }


@app.post("/agent")
async def run_agent(
    req: AgentRequest,
    memory: SessionMemory = Depends(get_memory),
    cache: CacheService = Depends(get_cache),
    multi_agent: MultiAgentCoordinator = Depends(get_multi_agent),
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

            result = await multi_agent.run(req.query, history=history)
            result["cache_hit"] = False
            await memory.add_turn(req.session_id, "user", req.query)
            await memory.add_turn(req.session_id, "assistant", result.get("answer", ""))
            await cache.set(req.session_id, req.query, result, fp)
            return JSONResponse(result)
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"code": "AGENT_FAILED", "message": str(exc)}) from exc
