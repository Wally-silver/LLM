# API 示例

## GET /health
```bash
curl http://127.0.0.1:8000/health
```
响应（示例）
```json
{"status":"ok","redis_available":true,"neo4j":{"enabled":false,"connected":false}}
```

## GET /system/status
```bash
curl http://127.0.0.1:8000/system/status
```

## GET /rag/stats
```bash
curl http://127.0.0.1:8000/rag/stats
```

## POST /datasources/ingest
```bash
curl -X POST http://127.0.0.1:8000/datasources/ingest \
  -H "Content-Type: application/json" \
  -d '{"source_type":"directory","source_value":"data/knowledge_base","recursive":true,"overwrite":true}'
```

## GET /documents
```bash
curl http://127.0.0.1:8000/documents
```

## POST /ask
```bash
curl -X POST http://127.0.0.1:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"session_id":"demo","query":"白夜第一次出场说了什么？","stream":false,"use_rag":true,"show_retrieval":true}'
```

## POST /ask/compare
```bash
curl -X POST http://127.0.0.1:8000/ask/compare \
  -H "Content-Type: application/json" \
  -d '{"session_id":"demo","query":"现实锚定值是什么意思？","stream":false,"show_retrieval":true}'
```
