import { useEffect, useMemo, useState } from 'react'

type RAGStats = {
  document_count: number
  source_count: number
  chunk_count: number
  index_ready: boolean
  embedding_model: string
  reranker_model: string
  neo4j_enabled: boolean
  neo4j_connected: boolean
}

type Doc = {
  doc_id: string
  title?: string
  source_type: string
  source_value: string
  metadata?: Record<string, unknown>
}

type Hit = {
  doc_id: string
  title?: string
  source_type?: string
  source_value?: string
  score?: number
  snippet: string
}

const sampleQuestion = '林樱第一次在什么场景觉醒了灵火？'

export function App() {
  const [baseUrl, setBaseUrl] = useState(import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000')
  const [stats, setStats] = useState<RAGStats | null>(null)
  const [system, setSystem] = useState<any>(null)
  const [docs, setDocs] = useState<Doc[]>([])
  const [query, setQuery] = useState(sampleQuestion)
  const [useRag, setUseRag] = useState(true)
  const [showRetrieval, setShowRetrieval] = useState(true)
  const [answer, setAnswer] = useState<any>(null)
  const [compare, setCompare] = useState<any>(null)
  const [ingestType, setIngestType] = useState('directory')
  const [ingestValue, setIngestValue] = useState('data/knowledge_base')
  const [inlineText, setInlineText] = useState('')
  const [ingestResult, setIngestResult] = useState<any>(null)

  const api = useMemo(() => ({
    get: async (path: string) => fetch(`${baseUrl}${path}`).then(r => r.json()),
    post: async (path: string, body: unknown) => fetch(`${baseUrl}${path}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body)}).then(r => r.json()),
    delete: async (path: string) => fetch(`${baseUrl}${path}`, { method: 'DELETE'}).then(r => r.json()),
  }), [baseUrl])

  const refreshAll = async () => {
    const [s, d, sys] = await Promise.all([api.get('/rag/stats'), api.get('/documents'), api.get('/system/status')])
    setStats(s)
    setDocs(d.documents ?? [])
    setSystem(sys)
  }

  useEffect(() => { refreshAll().catch(console.error) }, [api])

  const ingest = async () => {
    const payload = {
      source_type: ingestType,
      source_value: ingestType === 'inline' ? inlineText : ingestValue,
      recursive: true,
      overwrite: true,
    }
    const out = await api.post('/datasources/ingest', payload)
    setIngestResult(out)
    await refreshAll()
  }

  const ask = async () => {
    const out = await api.post('/ask', { session_id: 'demo-session', query, stream: false, use_rag: useRag, show_retrieval: showRetrieval })
    setAnswer(out)
  }

  const askCompare = async () => {
    const out = await api.post('/ask/compare', { session_id: 'demo-session', query, stream: false, show_retrieval: true })
    setCompare(out)
  }

  const deleteDoc = async (docId: string) => {
    await api.delete(`/documents/${docId}`)
    await refreshAll()
  }

  return (
    <div className="page">
      <h1>小说型 RAG 演示系统</h1>
      <div className="panel">
        <label>API Base URL</label>
        <input value={baseUrl} onChange={e => setBaseUrl(e.target.value)} />
        <button onClick={refreshAll}>刷新状态</button>
      </div>

      <div className="grid2">
        <section className="panel">
          <h2>知识库导入区</h2>
          <select value={ingestType} onChange={e => setIngestType(e.target.value)}>
            <option value="directory">directory</option>
            <option value="file">file</option>
            <option value="url">url</option>
            <option value="inline">inline</option>
            <option value="json">json</option>
            <option value="jsonl">jsonl</option>
            <option value="csv">csv</option>
          </select>
          {ingestType !== 'inline' ? <input value={ingestValue} onChange={e => setIngestValue(e.target.value)} /> : <textarea rows={6} value={inlineText} onChange={e => setInlineText(e.target.value)} />}
          <button onClick={ingest}>导入</button>
          {ingestResult && <pre>{JSON.stringify(ingestResult, null, 2)}</pre>}
        </section>

        <section className="panel">
          <h2>知识库状态区</h2>
          {stats && (
            <ul>
              <li>文档数: {stats.document_count}</li>
              <li>Chunk 数: {stats.chunk_count}</li>
              <li>数据源数: {stats.source_count}</li>
              <li>索引就绪: {String(stats.index_ready)}</li>
              <li>Embedding: {stats.embedding_model}</li>
              <li>Reranker: {stats.reranker_model}</li>
              <li>Neo4j: {String(stats.neo4j_enabled)} / connected={String(stats.neo4j_connected)}</li>
              <li>Redis: {String(system?.redis?.available)}</li>
            </ul>
          )}
        </section>
      </div>

      <section className="panel">
        <h2>问答区</h2>
        <textarea rows={4} value={query} onChange={e => setQuery(e.target.value)} />
        <div className="row">
          <label><input type="checkbox" checked={useRag} onChange={e => setUseRag(e.target.checked)} /> 使用 RAG</label>
          <label><input type="checkbox" checked={showRetrieval} onChange={e => setShowRetrieval(e.target.checked)} /> 显示检索结果</label>
          <button onClick={ask}>发送问题</button>
          <button onClick={askCompare}>对比模式</button>
        </div>
        {answer && (
          <div>
            <h3>回答（use_rag={String(answer.use_rag)}）</h3>
            <p>{answer.answer}</p>
            <small>latency={answer.latency_ms}ms cache={String(answer.cache_hit)}</small>
            {answer.retrieved_docs?.length > 0 && (
              <div>
                <h4>检索命中</h4>
                {answer.retrieved_docs.map((h: Hit, i: number) => (
                  <article key={i} className="hit">
                    <b>{h.title || h.doc_id}</b> <span>{h.source_type}</span> <span>{h.score?.toFixed?.(3)}</span>
                    <p>{h.snippet}</p>
                  </article>
                ))}
              </div>
            )}
          </div>
        )}
      </section>

      <section className="panel">
        <h2>对比区（核心演示）</h2>
        {compare ? (
          <div className="grid2">
            <article>
              <h3>不开 RAG</h3>
              <p>{compare.no_rag_answer}</p>
              <small>{compare.no_rag_latency_ms} ms</small>
            </article>
            <article>
              <h3>开 RAG</h3>
              <p>{compare.rag_answer}</p>
              <small>{compare.rag_latency_ms} ms (diff {compare.latency_diff_ms} ms)</small>
            </article>
            <article className="full">
              <h3>检索文档片段</h3>
              {compare.retrieved_docs?.map((h: Hit, i: number) => (
                <div key={i} className="hit">
                  <b>{h.title || h.doc_id}</b> <span>{h.source_value}</span>
                  <p>{h.snippet}</p>
                </div>
              ))}
            </article>
          </div>
        ) : <p>点击“对比模式”后会同时展示 no_rag 与 rag 回答差异。</p>}
      </section>

      <section className="panel">
        <h2>文档列表区</h2>
        <table>
          <thead><tr><th>doc_id</th><th>title</th><th>source</th><th>action</th></tr></thead>
          <tbody>
            {docs.map(d => (
              <tr key={d.doc_id}>
                <td>{d.doc_id}</td>
                <td>{d.title || '-'}</td>
                <td>{d.source_type}:{d.source_value}</td>
                <td><button onClick={() => deleteDoc(d.doc_id)}>删除</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  )
}
