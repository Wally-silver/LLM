import type { RAGStats, SystemStatus } from '../types'

type Props = {
  stats: RAGStats | null
  system: SystemStatus | null
  refreshing: boolean
  onRefresh: () => void
}

export function SystemStatusPanel({ stats, system, refreshing, onRefresh }: Props) {
  return (
    <section className="card">
      <div className="card-header">
        <h3>知识库状态</h3>
        <button disabled={refreshing} onClick={onRefresh}>{refreshing ? '刷新中...' : '刷新状态'}</button>
      </div>
      {!stats ? <p>暂无状态数据</p> : (
        <ul className="kv-list">
          <li><span>文档数</span><b>{stats.document_count}</b></li>
          <li><span>Chunk 数</span><b>{stats.chunk_count}</b></li>
          <li><span>数据源数</span><b>{stats.source_count}</b></li>
          <li><span>索引状态</span><b>{String(stats.index_ready)}</b></li>
          <li><span>Embedding</span><b>{stats.embedding_model}</b></li>
          <li><span>Reranker</span><b>{stats.reranker_model}</b></li>
        </ul>
      )}
      {system && (
        <>
        <ul className="kv-list">
          <li><span>LLM模型</span><b>{system.llm.model_name}</b></li>
          <li><span>LLM地址</span><b>{system.llm.base_url}</b></li>
        </ul>

        <div className="service-grid">
          <div className={`service-pill ${system.redis.available ? 'ok' : 'warn'}`}>Redis: {system.redis.available ? '可用' : '降级内存'}</div>
          <div className={`service-pill ${system.neo4j.connected ? 'ok' : 'warn'}`}>Neo4j: {system.neo4j.connected ? '已连接' : '未连接'}</div>
                  <div className={`service-pill ${system.llm.reachable ? "ok" : "warn"}`}>Ollama: {system.llm.reachable ? "已连接" : "未连接"}</div>
          {system.llm.models?.length > 0 && <div className="service-pill ok">Models: {system.llm.models.join(", ")}</div>}
        </div>
        </>
      )}
    </section>
  )
}
