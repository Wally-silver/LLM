# 小说型 RAG 使用说明

## 1. 知识库与评测集边界
- `data/eval/*`：评测数据，仅用于 `/eval/*`。
- `data/knowledge_base/*`：真实 RAG 知识库（可替换为你的小说/设定）。

## 2. 推荐目录结构

```text
data/knowledge_base/
  story.md
  characters.md
  timeline.md
  locations.md
  items.md
```

## 3. 导入方式
- 目录批量：`source_type=directory` + `source_value=data/knowledge_base`
- 单文件：`source_type=file` + 文件路径
- URL：`source_type=url`
- 直接文本：`source_type=inline`

## 4. 验证 RAG 是否生效
1. 先用 `/ask` 发送 `use_rag=false`。
2. 再发送同问题 `use_rag=true`。
3. 查看返回里的 `retrieved_docs`、`rag_context`。
4. 或直接使用 `/ask/compare` 一次得到对比结果。

## 5. Neo4j 角色
- 导入时将文档节点同步到 Neo4j（启用时）。
- 问答时可通过 `kg_hits` 返回图谱相关文本。
- Neo4j 状态在 `/system/status` 和 `/rag/stats` 中可见。

## 6. 已知限制
- 当前实体抽取为轻量实现（文档节点为主）。
- 超长文档建议拆分章节文件以获得更稳定检索。
- 若 Redis 不可用，系统自动降级为内存会话与缓存（重启丢失）。
