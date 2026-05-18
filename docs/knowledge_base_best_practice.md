# 小说知识库最佳实践

## 推荐结构
```text
data/knowledge_base/
  story/
    chapter_001.md
    chapter_002.md
  characters.md
  timeline.md
  locations.md
  items.md
```

## 长篇小说拆分建议
- 每章单独文件，文件名带章节号。
- 一章过长时按场景再拆分。
- 保留对话与段落，不要压缩成一整段。

## 设定文档组织
- `characters.md`：角色名、身份、关系、关键事件。
- `timeline.md`：按时间顺序列事件。
- `locations.md`：地点特征、首次出现章节。
- `items.md`：道具来源、持有者变化、作用。

## 适合测试 RAG 的问题
- 事实定位类：首次出现、谁说过什么、事件顺序。
- 关系追踪类：角色关系变化、道具流转。
- 多文档汇总类：正文 + 角色表 + 时间线交叉验证。

## 不适合单靠 RAG 的问题
- 超开放创作问题（如“续写十万字”）。
- 需要外部世界知识但知识库未覆盖的问题。

## 如何判断 RAG 真正生效
1. 同问题分别请求 `use_rag=false` 与 `use_rag=true`。
2. 观察 `/ask/compare` 中回答差异。
3. 检查 `retrieved_docs` 是否命中正确来源。
4. 回答里是否体现知识库特有细节（章节事实）。
