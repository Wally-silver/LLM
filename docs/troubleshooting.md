# Troubleshooting

## 1) `/health` 报错
- 先看 `/system/status`：确认 Redis / Neo4j 状态。
- 检查后端日志是否有模型初始化异常（embedding/reranker/llm）。

## 2) Redis 不可用
- 现象：`/system/status` 显示 `redis.available=false`。
- 说明：系统自动降级到内存缓存/会话，重启后历史丢失。
- 处理：启动 Redis 并检查 `REDIS_URL`。

## 3) Neo4j 未连接
- 现象：`neo4j.connected=false`。
- 处理步骤：
  1. 检查 `NEO4J_URI/USERNAME/PASSWORD`。
  2. 确认数据库服务可连通（bolt 端口）。
  3. 看 `/system/status.neo4j.error` 具体错误。

## 4) embedding / reranker 下载失败
- 现象：首次构建索引很慢或报网络错误。
- 处理：
  - 确保可访问 HuggingFace。
  - 使用镜像或提前手动下载模型。
  - 在离线环境准备模型缓存目录。

## 5) ingest 后 `chunk_count` 未变化
- 常见原因：
  - 导入文件为空/解析失败（看 ingest 的 `errors` 字段）。
  - 文档被 `overwrite=false` 跳过。
  - 导入类型与文件内容不匹配。
- 建议：导入后调用 `/rag/rebuild`，再看 `/rag/stats`。

## 6) 问答无检索结果
- 检查 `retrieved_docs` 是否为空。
- 提问应包含明确实体（角色名/地点/事件名）。
- 确认知识库文本中确实包含对应信息。
- 必要时增加 `RAG_TOP_K` 或优化分块。

## 7) 前端请求失败 / base URL 错误
- 确认前端顶部 `API Base URL` 与后端端口一致。
- 确认后端已启动且 CORS 未被代理层阻断。
- 查看浏览器 Network 响应体中的错误详情。

## 8) 文档格式支持与解析失败
- 支持：`txt/md/pdf/docx/json/jsonl/csv`。
- PDF 依赖 `pypdf`，DOCX 依赖 `python-docx`。
- 若缺依赖会在 ingest `errors` 中看到对应报错。
