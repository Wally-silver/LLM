# 小说型 RAG 对比演示系统（FastAPI + React + Neo4j）

本项目已升级为可直接演示的**小说知识库 RAG 系统**：
- 导入你自己的小说正文/设定文档作为真实知识库（非 mock）
- 页面内一键对比：**不开 RAG** vs **开 RAG**
- 可查看检索命中文档片段、来源、分数、知识库统计
- 可查看 Neo4j / Redis 状态并支持降级

---

## 一、功能总览

### 后端能力
- 文档导入：`txt/md/pdf/docx/json/jsonl/csv`，支持目录批量。
- 问答开关：`POST /ask` 支持 `use_rag=true/false`。
- 对比问答：`POST /ask/compare` 同时返回 no_rag 与 rag 结果。
- 结构化检索返回：`retrieved_docs` 包含 `doc_id/title/source/score/snippet/metadata`。
- 文档管理：列表、删除、重建索引、状态查询。
- Neo4j 集成：导入时 upsert 文档节点，问答时可返回 `kg_hits`。
- Redis 降级：Redis 不可用时自动切内存缓存/会话。

### 前端能力（`frontend/`）
- 知识库导入区（directory/file/url/inline/json/jsonl/csv）
- 知识库状态区（文档数/chunk数/source数/index、embedding/reranker、Neo4j/Redis）
- 问答区（use_rag 开关 + 检索结果展示）
- 对比区（一次展示 no_rag 与 rag 的回答差异）
- 文档列表区（查看与删除）

---

## 二、快速启动

## 1) 启动后端
```bash
pip install -e .
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## 2) 启动前端
```bash
cd frontend
npm install
npm run dev
```
默认前端地址：`http://127.0.0.1:5173`

前端默认后端地址：`http://127.0.0.1:8000`（可在页面顶部修改）

---

## 三、小说知识库导入

默认已提供可替换模板目录：`data/knowledge_base/`。

### 推荐目录结构
```text
data/knowledge_base/
  story.md
  characters.md
  timeline.md
  locations.md
  items.md
```

### API 导入示例
```bash
curl -X POST http://127.0.0.1:8000/datasources/ingest \
  -H "Content-Type: application/json" \
  -d '{"source_type":"directory","source_value":"data/knowledge_base","recursive":true,"overwrite":true}'
```

---

## 四、问答与对比

### 普通问答（不开 RAG）
```bash
curl -X POST http://127.0.0.1:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"session_id":"demo","query":"林樱第一次在哪里觉醒灵火？","stream":false,"use_rag":false}'
```

### 普通问答（开 RAG）
```bash
curl -X POST http://127.0.0.1:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"session_id":"demo","query":"林樱第一次在哪里觉醒灵火？","stream":false,"use_rag":true,"show_retrieval":true}'
```

### 一次请求直接对比（核心）
```bash
curl -X POST http://127.0.0.1:8000/ask/compare \
  -H "Content-Type: application/json" \
  -d '{"session_id":"demo","query":"白夜第一次自我介绍说了什么？","stream":false}'
```

---

## 五、评测数据与真实知识库边界（必须区分）

- `data/eval/*.jsonl`：评测集（仅用于 `/eval/*`）。
- `data/knowledge_base/*`：真实知识库（你自己的小说/设定文档）。

> 本次升级已将两者用途明确分离，不混用。

---

## 六、Neo4j 当前角色

1. 导入时同步写入文档节点（`Document`）。
2. 问答时可返回图谱检索补充（`kg_hits`）。
3. 可通过 `/system/status` 和 `/rag/stats` 查看是否启用/连接成功。

---

## 七、关键文件职责与函数调用链

### 后端文件职责
- `app/main.py`：路由、编排、降级、compare 流程。
- `app/schemas.py`：所有请求/响应结构。
- `app/services/datasource.py`：多格式文档加载。
- `app/services/document_store.py`：文档持久化与管理。
- `app/services/rag.py`：分块、向量、检索、重排。
- `app/services/knowledge_graph.py`：Neo4j 读写与状态。
- `app/services/runtime_fallback.py`：Redis 降级方案。
- `frontend/src/App.tsx`：演示页面主逻辑。

### 核心调用流向
1. **导入链路**
`/datasources/ingest` -> `load_many` -> `bulk_upsert` -> `build_index` -> `upsert_document`(Neo4j)

2. **问答链路（use_rag=false）**
`/ask` -> `_run_single_answer(use_rag=False)` -> `LLM.complete`

3. **问答链路（use_rag=true）**
`/ask` -> `_run_single_answer(use_rag=True)` -> `RAG.retrieve` + `KG.search_related` -> `LLM.complete`

4. **对比链路**
`/ask/compare` -> 并行两次 `_run_single_answer`（no_rag + rag）-> 合并响应

---

## 八、文档
- `docs/novel_rag_guide.md`：面向使用者的小说知识库接入说明。
- `docs/backend_call_flow.md`：后端职责与调用链详解。

---

## 九、当前限制与扩展方向
- 目前 Neo4j 以文档节点为主，实体抽取关系可继续增强。
- 超长小说推荐按章节拆分以提升检索稳定性。
- 前端目前为单页演示版，可后续增强鉴权、上传组件、图谱可视化。
