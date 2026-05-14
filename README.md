# 小说型 RAG 对比演示系统（FastAPI + React + TypeScript）

> 目标：把你的**整篇小说正文 + 设定文档**作为真实知识库导入，并在页面上直观看到「不开 RAG」和「开 RAG」的回答差异。

---

## 1. 项目适用范围

适合：
- 小说 / 轻小说 / 世界观设定 / 角色档案 / 时间线问答
- 演示“RAG是否真正生效”的场景
- 本地私有化部署（可选 Redis / Neo4j）

不适合：
- 纯生成创作平台（如长期写作助手）
- 高并发生产级服务（当前更偏演示与工程样例）

---

## 2. 环境依赖检查清单

- Python 3.11+
- Node.js 18+
- （可选）Redis
- （可选）Neo4j
- LLM 服务（Ollama 或 OpenAI-compatible）

配置模板见：`.env.example`。

---

## 3. 快速启动

### 3.1 后端
```bash
pip install -e .
cp .env.example .env
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 3.2 前端
```bash
cd frontend
npm install
npm run dev
```
默认：`http://127.0.0.1:5173`

---

## 4. 外部服务准备

### Redis（可选）
- 配置 `REDIS_URL`。
- 不可用时会自动降级内存模式（会话/缓存不持久）。

### Neo4j（可选）
- 配置 `NEO4J_URI/USERNAME/PASSWORD/DATABASE`。
- 不可用时不阻塞主 RAG 流程，可在 `/system/status` 查看错误。

### LLM
- `LLM_PROVIDER=ollama` 时建议先拉模型。
- 或配置 OpenAI-compatible 网关地址与 key。

---

## 5. 知识库与评测集边界

- `data/knowledge_base/*`：真实知识库（你的小说全文、角色表、时间线等）
- `data/eval/*`：评测数据（仅 `/eval/*` 用）

二者**不可混用**。

---

## 6. 小说知识库导入

默认提供目录：`data/knowledge_base/`（可替换成你的完整小说）

```bash
curl -X POST http://127.0.0.1:8000/datasources/ingest \
  -H "Content-Type: application/json" \
  -d '{"source_type":"directory","source_value":"data/knowledge_base","recursive":true,"overwrite":true}'
```

支持格式：`txt/md/pdf/docx/json/jsonl/csv`

---

## 7. 对比问答（核心）

### 普通问答（use_rag 可开关）
```bash
curl -X POST http://127.0.0.1:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"session_id":"demo","query":"白夜第一次说了什么？","stream":false,"use_rag":true,"show_retrieval":true}'
```

### 一次返回 no-rag 与 rag
```bash
curl -X POST http://127.0.0.1:8000/ask/compare \
  -H "Content-Type: application/json" \
  -d '{"session_id":"demo","query":"现实锚定值是什么？","stream":false,"show_retrieval":true}'
```

响应中重点关注：
- `no_rag_answer`
- `rag_answer`
- `retrieved_docs`
- `rag_context`

---

## 8. API 返回示例（简化）

### `/rag/stats`
```json
{
  "document_count": 42,
  "source_count": 5,
  "chunk_count": 366,
  "index_ready": true,
  "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
  "reranker_model": "cross-encoder/ms-marco-MiniLM-L-6-v2",
  "neo4j_enabled": true,
  "neo4j_connected": false
}
```

### `/ask/compare`
```json
{
  "query": "林樱第一次在哪里觉醒灵火？",
  "no_rag_answer": "...",
  "rag_answer": "...",
  "retrieved_docs": [{"doc_id":"...","title":"story","score":0.87,"snippet":"..."}],
  "no_rag_latency_ms": 1020,
  "rag_latency_ms": 1330,
  "latency_diff_ms": 310
}
```

完整示例见：`docs/api_examples.md`。

---

## 9. 前端结构（工程化）

- `frontend/src/lib/api.ts`：统一 API 层（GET/POST/DELETE + 非200错误处理）
- `frontend/src/types.ts`：统一类型定义
- `frontend/src/components/*`：拆分面板组件（导入/状态/问答/对比/文档表/空状态）
- `frontend/src/App.tsx`：页面编排与全局状态

---

## 10. 文档索引

- `docs/novel_rag_guide.md`：使用指南
- `docs/knowledge_base_best_practice.md`：知识库组织最佳实践
- `docs/api_examples.md`：API 调用示例
- `docs/troubleshooting.md`：排障手册
- `docs/backend_call_flow.md`：后端职责与调用链

---

## 11. 当前限制与后续可扩展

- Neo4j 目前以文档节点检索为主，实体/关系抽取可继续增强。
- 前端为演示型控制台，后续可加鉴权、多用户、图谱可视化。
- 模型下载依赖网络；离线环境需预热 embedding/reranker 缓存。


## 12. Stream 模式说明（重要）

- **前端默认 `stream=false`**，以确保：
  - `use_rag=false` 与 `use_rag=true` 的行为隔离清晰；
  - 指标（如 `retrieval_metrics`）在非流式分支稳定返回。
- 当前 `/ask` 的 `stream=true` 主要用于 token 实时输出（SSE），不包含完整结构化指标聚合。
- 若你要做 RAG/no-RAG 严格对比或观测检索指标，建议使用：
  - `/ask` + `stream=false`
  - `/ask/compare`（内部强制两路都走 `stream=false`，避免串流干扰）

补充：当 `use_rag=false` 时，后端会显式返回空检索指标（`embedding_latency_ms=0`、`vector_search_latency_ms=0` 等），便于前端统一渲染与统计。

---



## 配置优先级与离线模型提示
- `.env` 优先级高于 `app/config.py` 默认值。
- 若 `.env` 中 `EMBEDDING_MODEL` / `RERANK_MODEL` 使用 HuggingFace 在线仓库名，离线环境会失败。
- 离线运行请改为本地模型路径。
