type Metrics = {
  top_k: number
  retrieved_count: number
  hit_rate: number
  avg_score?: number | null
  max_score?: number | null
  min_score?: number | null
  embedding_latency_ms: number
  vector_search_latency_ms: number
  retrieval_latency_ms: number
  rerank_latency_ms: number
  total_retrieval_latency_ms: number
}

export function RetrievalMetricsPanel({ metrics }: { metrics?: Metrics | null }) {
  if (!metrics) return null
  return (
    <section className="card">
      <h4>检索指标</h4>
      <small>说明：Top-K填充率 = retrieved_count / top_k（非严格学术召回率）</small>
      <div className="metrics-grid">
        <div>Top-K: <b>{metrics.top_k}</b></div>
        <div>召回片段数: <b>{metrics.retrieved_count}</b></div>
        <div>Top-K填充率: <b>{(metrics.hit_rate * 100).toFixed(1)}%</b></div>
        <div>平均分: <b>{metrics.avg_score?.toFixed?.(3) ?? '-'}</b></div>
        <div>最高分: <b>{metrics.max_score?.toFixed?.(3) ?? '-'}</b></div>
        <div>最低分: <b>{metrics.min_score?.toFixed?.(3) ?? '-'}</b></div>
        <div>向量化耗时: <b>{metrics.embedding_latency_ms}ms</b></div>
        <div>向量检索耗时: <b>{metrics.vector_search_latency_ms}ms</b></div>
        <div>检索耗时: <b>{metrics.retrieval_latency_ms}ms</b></div>
        <div>重排耗时: <b>{metrics.rerank_latency_ms}ms</b></div>
        <div>总耗时: <b>{metrics.total_retrieval_latency_ms}ms</b></div>
      </div>
    </section>
  )
}
