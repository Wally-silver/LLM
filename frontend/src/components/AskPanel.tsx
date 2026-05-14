import type { AskResponse } from '../types'
import { EmptyState } from './EmptyState'
import { RetrievalMetricsPanel } from './RetrievalMetricsPanel'

type Props = {
  query: string
  setQuery: (q: string) => void
  showRetrieval: boolean
  setShowRetrieval: (v: boolean) => void
  asking: boolean
  answer: AskResponse | null
  onAsk: () => Promise<void>
  mode: 'ask' | 'rag' | 'compare' | 'agent'
}

const presets = [
  '林樱第一次在哪里觉醒灵火？',
  '白夜第一次出场时说了什么？',
  '小桃在剧情中的真实身份是什么？',
  '现实锚定值是什么机制？',
]

export function AskPanel(props: Props) {
  const { query, setQuery, showRetrieval, setShowRetrieval, asking, answer, onAsk, mode } = props

  return (
    <section className="card">
      <h3>{mode === 'rag' ? 'RAG知识库问答' : mode === 'agent' ? 'Agent任务执行' : '普通问答'}</h3>
      <div className="preset-row">
        {presets.map(q => <button key={q} className="ghost" onClick={() => setQuery(q)}>{q}</button>)}
      </div>
      <textarea rows={4} value={query} onChange={e => setQuery(e.target.value)} />
      <div className="controls">
        {mode === 'rag' && (
          <label><input type="checkbox" checked={showRetrieval} onChange={e => setShowRetrieval(e.target.checked)} /> 显示检索结果</label>
        )}
        <button disabled={asking} onClick={onAsk}>{asking ? '生成中...' : '发送'}</button>
      </div>

      {!answer ? <EmptyState title="等待提问" description="输入问题后点击发送。" /> : (
        <div className="answer-wrap">
          <div className={`answer-card ${answer.use_rag ? 'rag' : 'no-rag'}`}>
            <h4>{answer.use_rag ? '开 RAG 回答' : '不开 RAG 回答'}</h4>
            <p>{answer.answer}</p>
            <small>latency={answer.latency_ms}ms / cache={String(answer.cache_hit)}</small>
          </div>
          {mode === 'rag' && <RetrievalMetricsPanel metrics={answer.metadata?.retrieval_metrics as any} />}
          <div>
            <h4>检索结果</h4>
            {answer.retrieved_docs.length === 0 ? <EmptyState title="未检索到片段" description="可尝试更具体问题、提高 top-k 或确认知识库是否导入成功。" /> : (
              answer.retrieved_docs.map((hit, i) => (
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
          </div>
        </div>
      )}
    </section>
  )
}
