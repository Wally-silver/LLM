from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
import redis.asyncio as redis
from fastapi import Depends, FastAPI, HTTPException, Request, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from app.config import settings
from app.schemas import (
    AgentRequest,
    AskRequest,
    AskResult,
    Citation,
    CompareResponse,
    IngestSourceRequest,
    RAGStats,
    RetrievalMetrics,
    RetrievedHit,
    SourceInfo,
    ChatSession,
    ChatMessage,
    CreateSessionRequest,
    RenameSessionRequest,
    ChatRequest,
)
from app.services.agent_graph import AgentOrchestrator
from app.services.cache import CacheService
from app.services.llm_client import ModelNotFoundError, VLLMOpenAIClient
from app.services.memory import SessionMemory
from app.services.metrics import Metrics
from app.services.prompting import SYSTEM_PROMPT, build_no_rag_prompt, build_rag_prompt, build_user_prompt, extract_json, history_fingerprint
from app.services.rag import RAGService
from app.services.tools import Tool, ToolRegistry
from app.services.datasource import DataSourceService
from app.services.knowledge_graph import KnowledgeGraphService
from app.services.evaluator import AutoEvaluator, AgentQualityEvaluator
from app.services.document_store import DocumentStore
from app.services.runtime_fallback import InMemoryCacheService, InMemorySessionMemory
from app.services.multi_agent import MultiAgentCoordinator
from app.services.chat_store import InMemoryChatStore, RedisChatStore
from app.domain.windows_it_admin import WINDOWS_IT_ADMIN_SOURCES, WINDOWS_IT_ADMIN_TASKS
from app.domain.advanced_reasoning import (
    ADVANCED_REASONING_DATASET_CATALOG,
    ADVANCED_REASONING_SOURCES,
    ADVANCED_REASONING_TASKS,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    redis_client = None
    redis_available = False
    redis_error = None
    try:
        redis_client = redis.from_url(settings.redis_url, encoding="utf-8", decode_responses=True)
        await redis_client.ping()
        redis_available = True
    except Exception as exc:
        redis_error = str(exc)
        redis_client = None
    http_client = httpx.AsyncClient(timeout=settings.llm_timeout_seconds)

    if redis_available:
        memory = SessionMemory(redis_client, ttl_seconds=settings.memory_ttl_seconds)
        cache = CacheService(
            redis_client,
            ttl_seconds=settings.cache_ttl_seconds,
            jitter_seconds=settings.cache_jitter_seconds,
            lock_seconds=settings.cache_lock_seconds,
        )
    else:
        memory = InMemorySessionMemory(ttl_seconds=settings.memory_ttl_seconds)
        cache = InMemoryCacheService(
            ttl_seconds=settings.cache_ttl_seconds,
            lock_seconds=settings.cache_lock_seconds,
        )
    chat_store = RedisChatStore(redis_client) if redis_available else InMemoryChatStore()
    metrics = Metrics(redis_client if redis_available else None, window_size=settings.metrics_window_size)
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
    docs_store = DocumentStore()

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

    # 启动时尝试加载默认演示知识库目录（中等规模）
    demo_dir = Path("data/knowledge_base")
    if demo_dir.exists():
        demo_result = await datasource.load_many("directory", str(demo_dir), recursive=True)
        docs_store.bulk_upsert(demo_result.documents, overwrite=False)
    if docs_store.stats().document_count == 0:
        docs_store.bulk_upsert([
            datasource._normalize_doc("inline", "bootstrap", "RAG combines retrieval and generation to reduce hallucination and improve factuality.", title="bootstrap-1", metadata={"section": "bootstrap"}),
            datasource._normalize_doc("inline", "bootstrap", "vLLM improves throughput via paged KV cache and continuous batching.", title="bootstrap-2", metadata={"section": "bootstrap"}),
        ])
    await rag.build_index(docs_store.all_docs_for_index())

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

    print(f"[startup] embedding_model={settings.embedding_model}")
    print(f"[startup] rerank_model={settings.rerank_model}")
    print(f"[startup] llm_model_name={settings.llm_model_name}")
    print(f"[startup] openai_compatible_base_url={settings.openai_compatible_base_url}")

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
    app.state.chat_store = chat_store
    app.state.redis_available = redis_available
    app.state.redis_error = redis_error

    # 可选后台定时任务：示例每小时重建索引（演示热更新能力）
    stop_event = asyncio.Event()

    async def periodic_rebuild():
        while not stop_event.is_set():
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=3600)
            except asyncio.TimeoutError:
                await rag.build_index(docs_store.all_docs_for_index())

    task = asyncio.create_task(periodic_rebuild())
    try:
        yield
    finally:
        stop_event.set()
        task.cancel()
        await kg.close()
        if redis_client is not None:
            await redis_client.aclose()
        await http_client.aclose()


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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


def get_docs_store(request: Request) -> DocumentStore:
    return request.app.state.docs_store


def get_kg(request: Request) -> KnowledgeGraphService:
    return request.app.state.kg


def get_evaluator(request: Request) -> AutoEvaluator:
    return request.app.state.evaluator


def get_agent_quality_evaluator(request: Request) -> AgentQualityEvaluator:
    return request.app.state.agent_quality_evaluator


def get_multi_agent(request: Request) -> MultiAgentCoordinator:
    return request.app.state.multi_agent


def get_chat_store(request: Request):
    return request.app.state.chat_store


def _build_retrieved_hits(chunks, docs_store: DocumentStore) -> list[RetrievedHit]:
    hits: list[RetrievedHit] = []
    for c in chunks:
        doc = docs_store.get(c.doc_id)
        score = c.metadata.get("rerank_score") if isinstance(c.metadata, dict) else None
        hits.append(
            RetrievedHit(
                doc_id=c.doc_id,
                title=(doc.title if doc else None),
                source_type=(doc.source_type if doc else None),
                source_value=(doc.source_value if doc else None),
                score=float(score) if score is not None else None,
                snippet=c.text,
                metadata=(c.metadata if isinstance(c.metadata, dict) else {}),
            )
        )
    return hits


def _normalize_citations(raw) -> list[Citation]:
    out: list[Citation] = []
    if not raw:
        return out
    for item in raw:
        if isinstance(item, str):
            out.append(Citation(title=item))
        elif isinstance(item, dict):
            out.append(
                Citation(
                    title=str(item.get("title", "")),
                    url=str(item.get("url", "")),
                    snippet=str(item.get("snippet", "")),
                    score=float(item["score"]) if item.get("score") is not None else None,
                    source_id=item.get("source_id"),
                )
            )
    return out


async def _run_single_answer(
    *,
    req: AskRequest,
    llm: VLLMOpenAIClient,
    rag: RAGService,
    kg: KnowledgeGraphService,
    memory,
    use_rag: bool,
    docs_store: DocumentStore,
) -> AskResult:
    history = await memory.history_as_text(req.session_id)
    if use_rag and not rag.stats().get("indexed"):
        raise HTTPException(status_code=400, detail={"code": "EMPTY_KB", "message": "知识库为空，请先导入文档。"})
    chunks, retrieval_metrics = await rag.retrieve_with_metrics(req.query) if use_rag else ([], {
        "top_k": rag.top_k, "retrieved_count": 0, "hit_rate": 0.0, "avg_score": None, "max_score": None, "min_score": None,
        "embedding_latency_ms": 0, "vector_search_latency_ms": 0, "retrieval_latency_ms": 0, "rerank_latency_ms": 0, "total_retrieval_latency_ms": 0,
    })
    kg_related = []
    kg_status = {"enabled": False, "connected": False, "message": "Neo4j is not connected or KG tool is not configured."}
    if req.use_kg:
        st = kg.status()
        kg_status = {"enabled": bool(st.get("enabled")), "connected": bool(st.get("connected")), "message": "KG tool not configured." if st.get("connected") else "Neo4j is not connected or KG tool is not configured."}
        if use_rag and st.get("enabled") and st.get("connected"):
            kg_related = await kg.search_related(req.query, limit=3)
    context = "\n".join([f"[{c.doc_id}] {c.text}" for c in chunks] + kg_related) if use_rag else ""
    prompt = build_rag_prompt(req.query, context, history) if use_rag else build_no_rag_prompt(req.query, history)
    begin = time.perf_counter()
    output = await llm.complete(
        SYSTEM_PROMPT,
        prompt,
        stream=False,
        max_tokens=settings.llm_default_max_tokens,
        response_format={"type": "json_object"},
    )
    elapsed = int((time.perf_counter() - begin) * 1000)
    parsed = extract_json(output)
    return AskResult(
        answer=parsed.get("answer", output),
        use_rag=use_rag,
        rag_context=context if req.show_retrieval else "",
        retrieved_docs=_build_retrieved_hits(chunks, docs_store) if req.show_retrieval else [],
        kg_hits=[x.get("text", str(x)) if isinstance(x, dict) else str(x) for x in kg_related] if req.show_retrieval else [],
        citations=_normalize_citations(parsed.get("citations", []) if use_rag else []),
        used_tools=((parsed.get("used_tools", []) if isinstance(parsed.get("used_tools", []), list) else []) + (["rag_search"] if use_rag else []) + (["kg_search"] if req.use_kg and kg_related else [])),
        latency_ms=elapsed,
        metadata={**parsed.get("metadata", {}), "retrieval_metrics": retrieval_metrics, "kg_status": kg_status},
    )


@app.get("/health")
async def health(request: Request, metrics: Metrics = Depends(get_metrics), kg: KnowledgeGraphService = Depends(get_kg)):
    return {
        "status": "ok",
        "metrics": await metrics.snapshot(),
        "redis_available": bool(request.app.state.redis_available),
        "redis_error": request.app.state.redis_error,
        "neo4j": kg.status(),
    }


@app.post("/rag/rebuild")
async def rebuild_rag(rag: RAGService = Depends(get_rag), docs_store: DocumentStore = Depends(get_docs_store)):
    docs = docs_store.all_docs_for_index()
    await rag.build_index(docs)
    return {"ok": True, "docs": len(docs)}


@app.get("/datasources", response_model=list[SourceInfo])
async def list_datasources(docs_store: DocumentStore = Depends(get_docs_store)):
    return [
        SourceInfo(doc_id=v["doc_id"], source_type=v["source_type"], source_value=v["source_value"])
        for v in docs_store.list_sources()
    ]


@app.get("/documents")
async def list_documents(docs_store: DocumentStore = Depends(get_docs_store)):
    return {"documents": docs_store.list_sources()}


@app.delete("/documents/{doc_id}")
async def delete_document(
    doc_id: str,
    docs_store: DocumentStore = Depends(get_docs_store),
    rag: RAGService = Depends(get_rag),
):
    deleted = docs_store.delete_by_doc_id(doc_id)
    if not deleted:
        raise HTTPException(status_code=404, detail={"error": "doc_not_found", "doc_id": doc_id})
    await rag.build_index(docs_store.all_docs_for_index())
    return {"ok": True, "deleted_doc_id": doc_id}


@app.delete("/documents")
async def delete_documents_by_source(
    source_value: str,
    docs_store: DocumentStore = Depends(get_docs_store),
    rag: RAGService = Depends(get_rag),
):
    deleted = docs_store.delete_by_source(source_value)
    await rag.build_index(docs_store.all_docs_for_index())
    return {"ok": True, "deleted": deleted, "source_value": source_value}


@app.post("/datasources/bootstrap/windows-it-admin")
async def bootstrap_windows_it_admin(
    datasource: DataSourceService = Depends(get_datasource),
    docs_store: DocumentStore = Depends(get_docs_store),
    rag: RAGService = Depends(get_rag),
    kg: KnowledgeGraphService = Depends(get_kg),
):
    loaded = []
    for item in WINDOWS_IT_ADMIN_SOURCES:
        doc = await datasource.load(item["source_type"], item["source_value"], doc_id=item["doc_id"])
        doc.metadata.setdefault("tags", item.get("task_tags", []))
        docs_store.upsert(doc, overwrite=True)
        loaded.append(doc.doc_id)
        await kg.upsert_document(doc.doc_id, doc.source_type, doc.source_value, doc.text)
    docs_store.persist()
    await rag.build_index(docs_store.all_docs_for_index())
    return {"ok": True, "loaded_docs": loaded, "tasks": WINDOWS_IT_ADMIN_TASKS}


@app.get("/tasks/windows-it-admin")
async def windows_it_admin_tasks():
    return {"domain": "windows-it-admin", "tasks": WINDOWS_IT_ADMIN_TASKS}


@app.post("/datasources/bootstrap/advanced-reasoning")
async def bootstrap_advanced_reasoning(
    datasource: DataSourceService = Depends(get_datasource),
    docs_store: DocumentStore = Depends(get_docs_store),
    rag: RAGService = Depends(get_rag),
    kg: KnowledgeGraphService = Depends(get_kg),
):
    loaded = []
    for item in ADVANCED_REASONING_SOURCES:
        doc = await datasource.load(item["source_type"], item["source_value"], doc_id=item["doc_id"])
        doc.metadata.setdefault("tags", item.get("task_tags", []))
        docs_store.upsert(doc, overwrite=True)
        loaded.append(doc.doc_id)
        await kg.upsert_document(doc.doc_id, doc.source_type, doc.source_value, doc.text)
    docs_store.persist()
    await rag.build_index(docs_store.all_docs_for_index())
    return {"ok": True, "loaded_docs": loaded, "tasks": ADVANCED_REASONING_TASKS}


@app.get("/tasks/advanced-reasoning")
async def advanced_reasoning_tasks():
    return {"domain": "advanced-reasoning", "tasks": ADVANCED_REASONING_TASKS}


@app.get("/datasets/catalog")
async def datasets_catalog():
    return {"datasets": ADVANCED_REASONING_DATASET_CATALOG}


@app.get("/system/status")
async def system_status(request: Request, kg: KnowledgeGraphService = Depends(get_kg), llm: VLLMOpenAIClient = Depends(get_llm)):
    return {
        "redis": {"available": bool(request.app.state.redis_available), "error": request.app.state.redis_error},
        "neo4j": kg.status(),
        "kg_tool": {"enabled": False, "message": "KG tool not configured."},
        "llm": await llm.probe(),
    }


@app.get("/debug/rag")
async def debug_rag(q: str, rag: RAGService = Depends(get_rag), docs_store: DocumentStore = Depends(get_docs_store)):
    chunks, metrics = await rag.retrieve_with_metrics(q)
    hits = _build_retrieved_hits(chunks, docs_store)
    return {
        "query": q,
        "metrics": metrics,
        "hits": [
            {
                "rank": i + 1,
                "doc_id": h.doc_id,
                "snippet": h.snippet,
                "score": h.score,
                "source_type": h.source_type,
                "source_value": h.source_value,
            }
            for i, h in enumerate(hits)
        ],
    }


@app.get("/debug/kg/status")
async def debug_kg_status(kg: KnowledgeGraphService = Depends(get_kg)):
    return kg.status()


@app.get("/debug/kg/schema")
async def debug_kg_schema(kg: KnowledgeGraphService = Depends(get_kg)):
    return {"status": kg.status(), "schema": await kg.get_schema_summary()}


@app.get("/debug/kg/search")
async def debug_kg_search(q: str, kg: KnowledgeGraphService = Depends(get_kg)):
    return {"status": kg.status(), "hits": await kg.search_related(q, limit=10)}


@app.get("/debug/kg/path")
async def debug_kg_path(source: str, target: str, kg: KnowledgeGraphService = Depends(get_kg)):
    return {"status": kg.status(), "paths": await kg.find_paths(source, target, max_depth=3)}




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
    docs_store: DocumentStore = Depends(get_docs_store),
    rag: RAGService = Depends(get_rag),
    kg: KnowledgeGraphService = Depends(get_kg),
):
    result = await datasource.load_many(
        req.source_type,
        req.source_value,
        doc_id=req.doc_id,
        recursive=req.recursive,
    )
    if not result.documents:
        raise HTTPException(status_code=400, detail={"errors": result.errors or [{"error": "no_documents_loaded"}]})

    write_result = docs_store.bulk_upsert(result.documents, overwrite=req.overwrite)
    await rag.build_index(docs_store.all_docs_for_index())
    kg_errors = []
    for doc in result.documents:
        try:
            await kg.upsert_document(doc.doc_id, doc.source_type, doc.source_value, doc.text)
        except Exception as exc:
            kg_errors.append({"doc_id": doc.doc_id, "error": str(exc)})
    return {
        "ok": True,
        "inserted": write_result["inserted"],
        "skipped": write_result["skipped"],
        "total_docs": docs_store.stats().document_count,
        "errors": result.errors,
        "kg_errors": kg_errors,
        "neo4j": kg.status(),
    }


@app.get("/rag/stats", response_model=RAGStats)
async def rag_stats(
    rag: RAGService = Depends(get_rag),
    docs_store: DocumentStore = Depends(get_docs_store),
    kg: KnowledgeGraphService = Depends(get_kg),
):
    rag_snapshot = rag.stats()
    store_stats = docs_store.stats()
    kg_state = kg.status()
    return RAGStats(
        document_count=store_stats.document_count,
        source_count=store_stats.source_count,
        chunk_count=rag_snapshot["chunk_count"],
        index_ready=bool(rag_snapshot.get("indexed")),
        embedding_model=rag.embedding_model,
        reranker_model=rag.rerank_model,
        neo4j_enabled=bool(kg_state["enabled"]),
        neo4j_connected=bool(kg_state["connected"]),
    )


async def _non_stream_answer(
    req: AskRequest,
    memory,
    cache,
    llm: VLLMOpenAIClient,
    rag: RAGService,
    kg: KnowledgeGraphService,
    docs_store: DocumentStore,
):
    history = await memory.history_as_text(req.session_id)
    fp = history_fingerprint(history)
    mode = "rag" if req.use_rag else "no_rag"
    cache_key_query = f"{mode}|show={req.show_retrieval}|kg={req.use_kg}|model={settings.llm_model_name}|{req.query}"

    cached = await cache.get(req.session_id, cache_key_query, fp)
    if cached:
        cached["cache_hit"] = True
        return cached

    lock_acquired = await cache.acquire_lock(req.session_id, cache_key_query, fp)
    try:
        if not lock_acquired:
            # 避免击穿：等待已在计算中的请求写入缓存
            for _ in range(5):
                await asyncio.sleep(0.1)
                cached_retry = await cache.get(req.session_id, cache_key_query, fp)
                if cached_retry:
                    cached_retry["cache_hit"] = True
                    return cached_retry

        result = await _run_single_answer(
            req=req,
            llm=llm,
            rag=rag,
            kg=kg,
            memory=memory,
            use_rag=req.use_rag,
            docs_store=docs_store,
        )
        payload = result.model_dump()
        payload["cache_hit"] = False

        await memory.add_turn(req.session_id, "user", req.query)
        await memory.add_turn(req.session_id, "assistant", payload["answer"])
        await cache.set(req.session_id, cache_key_query, payload, fp)
        return payload
    finally:
        if lock_acquired:
            await cache.release_lock(req.session_id, cache_key_query, fp)


@app.post("/ask")
async def ask(
    req: AskRequest,
    memory = Depends(get_memory),
    cache = Depends(get_cache),
    llm: VLLMOpenAIClient = Depends(get_llm),
    rag: RAGService = Depends(get_rag),
    kg: KnowledgeGraphService = Depends(get_kg),
    metrics: Metrics = Depends(get_metrics),
    docs_store: DocumentStore = Depends(get_docs_store),
):
    try:
        async with metrics.track("/ask"):
            if req.stream:
                history = await memory.history_as_text(req.session_id)
                chunks = await rag.retrieve(req.query) if req.use_rag else []
                kg_related = []
                if req.use_rag and req.use_kg:
                    st = kg.status()
                    if st.get("enabled") and st.get("connected"):
                        kg_related = await kg.search_related(req.query, limit=3)
                context = "\n".join([f"[{c.doc_id}] {c.text}" for c in chunks] + kg_related) if req.use_rag else ""
                prompt = build_rag_prompt(req.query, context, history) if req.use_rag else build_no_rag_prompt(req.query, history)
                retrieved = _build_retrieved_hits(chunks, docs_store)

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
                    if req.use_rag and req.show_retrieval:
                        yield f"data: {json.dumps({'retrieved_docs': [x.model_dump() for x in retrieved], 'kg_hits': kg_related}, ensure_ascii=False)}\n\n"
                    await memory.add_turn(req.session_id, "user", req.query)
                    await memory.add_turn(req.session_id, "assistant", full_answer)

                return StreamingResponse(event_stream(), media_type="text/event-stream")

            result = await _non_stream_answer(req, memory, cache, llm, rag, kg, docs_store)
            return JSONResponse(result)
    except Exception as exc:
        msg = str(exc)
        if isinstance(exc, ModelNotFoundError) or "not found" in msg.lower() and "model" in msg.lower():
            msg = "模型未找到，请检查 LLM_MODEL_NAME 是否与 ollama list 输出一致。"
        elif any(x in msg.lower() for x in ["connection refused", "timeout", "ollama", "openai"]):
            msg = "LLM backend unavailable，请检查 Ollama 是否启动。"
        raise HTTPException(status_code=500, detail={"code": "ASK_FAILED", "message": msg}) from exc


@app.post("/ask/compare", response_model=CompareResponse)
async def ask_compare(
    req: AskRequest,
    llm: VLLMOpenAIClient = Depends(get_llm),
    rag: RAGService = Depends(get_rag),
    kg: KnowledgeGraphService = Depends(get_kg),
    memory=Depends(get_memory),
    metrics: Metrics = Depends(get_metrics),
    docs_store: DocumentStore = Depends(get_docs_store),
):
    try:
        async with metrics.track("/ask/compare"):
            req_no_rag = req.model_copy(update={"use_rag": False, "stream": False, "session_id": f"{req.session_id}:no_rag"})
            req_with_rag = req.model_copy(update={"use_rag": True, "stream": False, "session_id": f"{req.session_id}:rag"})
            no_rag_res = await _run_single_answer(
                req=req_no_rag,
                llm=llm,
                rag=rag,
                kg=kg,
                memory=memory,
                use_rag=False,
                docs_store=docs_store,
            )
            rag_res = await _run_single_answer(
                req=req_with_rag,
                llm=llm,
                rag=rag,
                kg=kg,
                memory=memory,
                use_rag=True,
                docs_store=docs_store,
            )
            await memory.add_turn(req.session_id, "user", req.query)
            await memory.add_turn(req.session_id, "assistant", f"[NO_RAG]{no_rag_res.answer}\n[RAG]{rag_res.answer}")
            return CompareResponse(
                query=req.query,
                no_rag_answer=no_rag_res.answer,
                rag_answer=rag_res.answer,
                rag_context=rag_res.rag_context,
                retrieved_docs=rag_res.retrieved_docs,
                kg_hits=rag_res.kg_hits,
                no_rag_latency_ms=no_rag_res.latency_ms,
                rag_latency_ms=rag_res.latency_ms,
                latency_diff_ms=rag_res.latency_ms - no_rag_res.latency_ms,
                rag_retrieval_metrics=rag_res.metadata.get("retrieval_metrics"),
            )
    except Exception as exc:
        msg = str(exc)
        if isinstance(exc, ModelNotFoundError) or "not found" in msg.lower() and "model" in msg.lower():
            msg = "模型未找到，请检查 LLM_MODEL_NAME 是否与 ollama list 输出一致。"
        elif any(x in msg.lower() for x in ["connection refused", "timeout", "ollama", "openai"]):
            msg = "LLM backend unavailable，请检查 Ollama 是否启动。"
        raise HTTPException(status_code=500, detail={"code": "COMPARE_FAILED", "message": msg}) from exc




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


@app.post("/sessions", response_model=ChatSession)
async def create_session(req: CreateSessionRequest, store=Depends(get_chat_store)):
    now = datetime.now(timezone.utc)
    sid = str(int(now.timestamp()*1000))
    session = {"id": sid, "title": req.title or "新对话", "created_at": now.isoformat(), "updated_at": now.isoformat(), "message_count": 0}
    await store.create_session(session)
    return session


@app.get("/sessions")
async def list_sessions(store=Depends(get_chat_store)):
    return {"sessions": await store.list_sessions()}


@app.get("/sessions/{session_id}")
async def get_session(session_id: str, store=Depends(get_chat_store)):
    s = await store.get_session(session_id)
    if not s:
        raise HTTPException(status_code=404, detail={"message": "session not found"})
    return s


@app.patch("/sessions/{session_id}")
async def rename_session(session_id: str, req: RenameSessionRequest, store=Depends(get_chat_store)):
    s = await store.update_session(session_id, {"title": req.title, "updated_at": datetime.now(timezone.utc).isoformat()})
    if not s:
        raise HTTPException(status_code=404, detail={"message": "session not found"})
    return s


@app.delete("/sessions/{session_id}")
async def delete_session(session_id: str, store=Depends(get_chat_store)):
    await store.delete_session(session_id)
    return {"ok": True}


@app.post("/chat", response_model=ChatMessage)
async def chat(req: ChatRequest, store=Depends(get_chat_store), memory=Depends(get_memory), cache=Depends(get_cache), llm: VLLMOpenAIClient = Depends(get_llm), rag: RAGService = Depends(get_rag), kg: KnowledgeGraphService = Depends(get_kg), metrics: Metrics = Depends(get_metrics), docs_store: DocumentStore = Depends(get_docs_store), multi_agent: MultiAgentCoordinator = Depends(get_multi_agent)):
    user_msg = {"id": str(int(time.time()*1000)), "session_id": req.session_id, "role": "user", "content": req.message, "mode": req.mode, "created_at": datetime.now(timezone.utc).isoformat(), "citations": [], "retrieved_docs": [], "retrieval_metrics": None, "kg_paths": [], "agent_trace": None, "used_tools": [], "raw": {}}
    await store.add_message(req.session_id, user_msg)
    session = await store.get_session(req.session_id)
    if session and session.get("title") == "新对话":
        await store.update_session(req.session_id, {"title": req.message[:20], "updated_at": datetime.now(timezone.utc).isoformat()})

    if req.mode == "compare":
        ar = AskRequest(session_id=req.session_id, query=req.message, stream=False, use_rag=True, show_retrieval=req.show_retrieval, use_kg=req.use_kg)
        out = await ask_compare(ar, llm, rag, kg, memory, metrics, docs_store)
        content = f"No-RAG: {out.no_rag_answer}\n\nRAG: {out.rag_answer}"
        assistant = {"id": str(int(time.time()*1000)+1), "session_id": req.session_id, "role": "assistant", "content": content, "mode": req.mode, "created_at": datetime.now(timezone.utc).isoformat(), "citations": [], "retrieved_docs": [x.model_dump() for x in out.retrieved_docs], "retrieval_metrics": out.rag_retrieval_metrics.model_dump() if out.rag_retrieval_metrics else None, "kg_paths": out.kg_hits, "agent_trace": None, "used_tools": [], "raw": out.model_dump()}
    elif req.mode == "agent":
        ar = AgentRequest(session_id=req.session_id, query=req.message, stream=False, use_rag=True, show_retrieval=True, use_kg=req.use_kg)
        out = await run_agent(ar, memory, cache, multi_agent, metrics)
        payload = json.loads(out.body.decode())
        assistant = {"id": str(int(time.time()*1000)+1), "session_id": req.session_id, "role": "assistant", "content": payload.get("answer", ""), "mode": req.mode, "created_at": datetime.now(timezone.utc).isoformat(), "citations": [], "retrieved_docs": [], "retrieval_metrics": None, "kg_paths": [], "agent_trace": payload.get("metadata", {}).get("final_state"), "used_tools": payload.get("used_tools", []), "raw": payload}
    else:
        use_rag = req.use_rag or req.mode in ["rag", "graph_rag"]
        use_kg = req.use_kg or req.mode in ["kg", "graph_rag"]
        ar = AskRequest(session_id=req.session_id, query=req.message, stream=False, use_rag=use_rag, show_retrieval=req.show_retrieval, use_kg=use_kg)
        out = await _non_stream_answer(ar, memory, cache, llm, rag, kg, docs_store)
        assistant = {"id": str(int(time.time()*1000)+1), "session_id": req.session_id, "role": "assistant", "content": out.get("answer", ""), "mode": req.mode, "created_at": datetime.now(timezone.utc).isoformat(), "citations": out.get("citations", []), "retrieved_docs": out.get("retrieved_docs", []), "retrieval_metrics": out.get("metadata", {}).get("retrieval_metrics"), "kg_paths": out.get("kg_hits", []), "agent_trace": None, "used_tools": out.get("used_tools", []), "raw": out}

    await store.add_message(req.session_id, assistant)
    return assistant


@app.post("/datasources/upload")
async def upload_datasource(file: UploadFile = File(...), datasource: DataSourceService = Depends(get_datasource), docs_store: DocumentStore = Depends(get_docs_store), rag: RAGService = Depends(get_rag)):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".txt", ".md", ".json", ".jsonl", ".csv", ".pdf", ".docx"}:
        raise HTTPException(status_code=400, detail={"message": "unsupported file type"})
    tmp = Path("/tmp") / (file.filename or f"upload{suffix}")
    tmp.write_bytes(await file.read())
    result = await datasource.load_many("file", str(tmp), recursive=False)
    if not result.documents:
        raise HTTPException(status_code=400, detail={"message": "no documents loaded", "errors": result.errors})
    write_result = docs_store.bulk_upsert(result.documents, overwrite=True)
    await rag.build_index(docs_store.all_docs_for_index())
    return {"ok": True, "inserted": write_result.get("inserted", 0), "docs": [d.doc_id for d in result.documents], "errors": result.errors}
