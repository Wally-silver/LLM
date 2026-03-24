# Industrial AI Agent (FastAPI + RAG + vLLM + LangGraph)

## 功能概览
- **FastAPI API层**：`/ask`（支持流式与非流式），`/agent`（LangGraph Agent执行）。
- **异步并发**：端到端 `async/await`。
- **RAG模块**：SentenceTransformer embedding + FAISS向量检索 + CrossEncoder精排 + query rewrite。
- **推理层**：通过OpenAI兼容协议调用vLLM，支持 `stream=True`。
- **Agent状态机**：Planner / Tool Executor / Retriever / Generator（ReAct风格）。
- **Tool Calling**：可注册工具（天气、RAG检索示例）。
- **Memory模块**：session级对话记忆，支持拼接历史（可扩展Redis）。
- **Redis缓存**：query结果缓存，TTL默认1小时。
- **结构化输出**：JSON约束与恢复。
- **评估监控**：记录请求延迟与缓存命中率。
- **可部署**：提供Dockerfile与K8s清单示例。

## 架构

```text
Client
  -> FastAPI (/ask, /agent)
       -> Cache (Redis)
       -> Memory (Session)
       -> Agent (LangGraph)
            Planner -> Tool Executor -> Retriever(RAG) -> LLM Generator(vLLM)
       -> Metrics
```

## 快速启动

```bash
pip install -e .
uvicorn app.main:app --reload --port 8080
```

## 启动vLLM（示例）

```bash
python -m vllm.entrypoints.openai.api_server \
  --model Qwen/Qwen2.5-7B-Instruct \
  --host 0.0.0.0 --port 8001
```

vLLM默认利用KV Cache与continuous batching提升吞吐。

## API示例

```bash
curl -X POST http://127.0.0.1:8080/ask \
  -H 'Content-Type: application/json' \
  -d '{"session_id":"s1","query":"RAG如何降低幻觉？","stream":false}'
```

```bash
curl -N -X POST http://127.0.0.1:8080/ask \
  -H 'Content-Type: application/json' \
  -d '{"session_id":"s1","query":"请流式输出","stream":true}'
```

```bash
curl -X POST http://127.0.0.1:8080/agent \
  -H 'Content-Type: application/json' \
  -d '{"session_id":"s1","query":"帮我查天气并结合知识库回答"}'
```
