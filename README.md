# Industrial AI Agent (Windows-ready + RAG Eval + Neo4j KG)

## 快速启动（Windows PowerShell）
```powershell
ollama pull qwen2.5:7b-instruct
pip install -e .
uvicorn app.main:app --host 0.0.0.0 --port 8080
```

## API
- `POST /ask`
- `POST /agent`（多Agent协作）
- `GET /health`
- `GET /datasources`
- `POST /datasources/ingest`
- `POST /datasources/bootstrap/windows-it-admin`
- `POST /datasources/bootstrap/advanced-reasoning`
- `GET /tasks/advanced-reasoning`
- `GET /datasets/catalog`
- `GET /eval/datasets`
- `POST /eval/run`
- `GET /agent/capabilities`
- `POST /rag/rebuild`

---

## 按 7 个数据集做自动评测
已内置 7 个可落地数据集目录（多跳 / 多轮 / 推荐 / 多模态）：
- HotpotQA
- 2WikiMultiHopQA
- MuSiQue
- MultiWOZ
- ReDial
- ScienceQA
- DocVQA

### 评测流程
1) 导入领域文档
```bash
curl -X POST http://127.0.0.1:8080/datasources/bootstrap/advanced-reasoning
```
2) 查看数据集目录
```bash
curl http://127.0.0.1:8080/datasets/catalog
```
3) 运行自动评测（EM/F1）
```bash
curl -X POST "http://127.0.0.1:8080/eval/run?limit_per_dataset=20"
```

> 默认使用每个数据集的 sample 子集进行自动回归；你可以扩展 `data/eval/*.jsonl` 到完整 benchmark。

---

## 知识图谱（Neo4j）融合
配置 `.env`：
```env
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your_password
NEO4J_DATABASE=neo4j
```

效果：
- 数据源导入时自动 upsert 文档节点到 Neo4j
- 问答时会把 KG 相关节点摘要拼接到 RAG context（Graph + Vector 混合检索）

---

## 高级任务（已替换，不再使用原先 4 个 Windows 操作任务）
1. 多跳推理问答（HotpotQA/2Wiki/MuSiQue）
2. 多轮任务型问答（MultiWOZ）
3. 个性化会话推荐（ReDial）
4. 多模态知识推理（ScienceQA + DocVQA）



## 多Agent协作链路
- task_router：任务类型路由
- retriever_agent：向量检索
- kg_agent：图谱检索
- tool_agent：工具调用
- reasoning_agent：生成草稿
- critic_agent：审查与修正
