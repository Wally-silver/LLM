import type { CompareResponse } from '../types'

export function CompareMessageCard({ raw }: { raw: Partial<CompareResponse> | any }) {
  const m = raw?.rag_retrieval_metrics
  const fill = m?.top_k ? ((m.retrieved_count / m.top_k) * 100).toFixed(1) : '-'
  return (
    <div className="compare-grid">
      <div className="card mini"><h4>No-RAG Answer</h4><p>{raw?.no_rag_answer || '-'}</p></div>
      <div className="card mini"><h4>RAG Answer</h4><p>{raw?.rag_answer || '-'}</p>
        <small>retrieved_count: {m?.retrieved_count ?? '-'}</small><br />
        <small>top_k_fill_rate: {fill}%</small><br />
        <small>avg_score: {m?.avg_score ?? '-'}</small><br />
        <small>total_retrieval_latency_ms: {m?.total_retrieval_latency_ms ?? '-'}</small>
      </div>
    </div>
  )
}
