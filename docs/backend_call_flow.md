# 后端文件职责与调用链

## 文件职责
- `app/main.py`：FastAPI 路由编排、生命周期、降级策略、RAG/Compare API。
- `app/schemas.py`：请求/响应结构（含 `use_rag`、`retrieved_docs`、`CompareResponse`）。
- `app/services/datasource.py`：多格式文档加载与标准化。
- `app/services/document_store.py`：文档持久层（JSON-backed）与删除/列表。
- `app/services/rag.py`：chunk/embed/retrieve/rerank。
- `app/services/knowledge_graph.py`：Neo4j 文档节点写入与检索。
- `app/services/runtime_fallback.py`：Redis 不可用时的内存会话/缓存。

## 核心调用链
1. 文档导入：
`/datasources/ingest` -> `DataSourceService.load_many` -> `DocumentStore.bulk_upsert` -> `RAGService.build_index` -> `KnowledgeGraphService.upsert_document`。

2. 普通问答：
`/ask` -> `_non_stream_answer` -> `_run_single_answer` -> (可选) `RAGService.retrieve` + `KnowledgeGraphService.search_related` -> `VLLMOpenAIClient.complete`。

3. 对比问答：
`/ask/compare` -> `_run_single_answer(use_rag=false)` + `_run_single_answer(use_rag=true)` -> 合并 `CompareResponse`。

4. 状态展示：
`/rag/stats` + `/system/status` + `/documents` 给前端仪表盘。
