import type { CompareResponse } from '../types'
import { EmptyState } from './EmptyState'

type Props = {
  comparing: boolean
  compare: CompareResponse | null
  onCompare: () => Promise<void>
}

export function ComparePanel({ comparing, compare, onCompare }: Props) {
  return (
    <section className="card">
      <div className="card-header">
        <h3>RAG 对比（核心演示）</h3>
        <button disabled={comparing} onClick={onCompare}>{comparing ? '对比中...' : '执行对比'}</button>
      </div>

      {!compare ? <EmptyState title="暂无对比结果" description="先在上方输入问题，然后点击执行对比。" /> : (
        <>
          <div className="compare-grid">
            <article className="answer-card no-rag">
              <h4>不开 RAG</h4>
              <p>{compare.no_rag_answer}</p>
              <small>{compare.no_rag_latency_ms}ms</small>
            </article>
            <article className="answer-card rag">
              <h4>开 RAG</h4>
              <p>{compare.rag_answer}</p>
              <small>{compare.rag_latency_ms}ms（差值 {compare.latency_diff_ms}ms）</small>
            </article>
          </div>
          <h4>对比检索片段</h4>
          {compare.retrieved_docs.length === 0 ? <EmptyState title="未检索到命中" description="这通常意味着问题太泛化或知识库中不存在该信息。" /> : (
            compare.retrieved_docs.map((hit, i) => (
              <article className="hit" key={`${hit.doc_id}-${i}`}>
                <div className="hit-head">
                  <b>{hit.title || hit.doc_id}</b>
                  <span>{hit.source_type}</span>
                  <span>{hit.score?.toFixed(3) ?? '-'}</span>
                </div>
                <small>{hit.source_value}</small>
                <p>{hit.snippet}</p>
              </article>
            ))
          )}
        </>
      )}
    </section>
  )
}
