import { useEffect, useMemo, useState } from 'react'
import { AskPanel } from './components/AskPanel'
import { ComparePanel } from './components/ComparePanel'
import { DocumentsTable } from './components/DocumentsTable'
import { KnowledgeIngestPanel } from './components/KnowledgeIngestPanel'
import { StatusBanner } from './components/StatusBanner'
import { SystemStatusPanel } from './components/SystemStatusPanel'
import { ApiClient } from './lib/api'
import type { AgentResponse, AskResponse, CompareResponse, DocumentInfo, IngestResponse, RAGStats, SystemStatus } from './types'

export function App() {
  const [baseUrl, setBaseUrl] = useState(import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000')
  const api = useMemo(() => new ApiClient(baseUrl), [baseUrl])

  const [stats, setStats] = useState<RAGStats | null>(null)
  const [system, setSystem] = useState<SystemStatus | null>(null)
  const [docs, setDocs] = useState<DocumentInfo[]>([])
  const [query, setQuery] = useState('林樱第一次在哪里觉醒灵火？')
  const [useRag, setUseRag] = useState(true)
  const [showRetrieval, setShowRetrieval] = useState(true)
  const [answer, setAnswer] = useState<AskResponse | null>(null)
  const [agentAnswer, setAgentAnswer] = useState<AgentResponse | null>(null)
  const [compare, setCompare] = useState<CompareResponse | null>(null)
  const [mode, setMode] = useState<'ask' | 'rag' | 'compare' | 'agent'>('rag')
  const [ingestResult, setIngestResult] = useState<IngestResponse | null>(null)

  const [refreshing, setRefreshing] = useState(false)
  const [ingesting, setIngesting] = useState(false)
  const [asking, setAsking] = useState(false)
  const [comparing, setComparing] = useState(false)
  const [deletingId, setDeletingId] = useState<string | null>(null)
  const [banner, setBanner] = useState<{ tone: 'success' | 'error' | 'info'; text: string } | null>(null)

  const refreshAll = async () => {
    setRefreshing(true)
    try {
      const [s, d, sys] = await Promise.all([api.getRagStats(), api.getDocuments(), api.getSystemStatus()])
      setStats(s)
      setDocs(d.documents)
      setSystem(sys)
      setBanner({ tone: 'success', text: '状态已刷新' })
    } catch (err: any) {
      setBanner({ tone: 'error', text: `刷新失败：${err.message}` })
    } finally {
      setRefreshing(false)
    }
  }

  const ingest = async (payload: { source_type: string; source_value: string; recursive: boolean; overwrite: boolean }) => {
    setIngesting(true)
    try {
      const out = await api.ingest(payload)
      setIngestResult(out)
      setBanner({ tone: 'success', text: `导入完成：+${out.inserted}，跳过 ${out.skipped}` })
      await refreshAll()
    } catch (err: any) {
      setBanner({ tone: 'error', text: `导入失败：${err.message}` })
    } finally {
      setIngesting(false)
    }
  }

  const ask = async () => {
    setAsking(true)
    try {
      const out = await api.ask({ session_id: 'demo-session', query, stream: false, use_rag: useRag, show_retrieval: showRetrieval })
      setAnswer(out)
      setAgentAnswer(null)
    } catch (err: any) {
      setBanner({ tone: 'error', text: `问答失败：${err.message}` })
    } finally {
      setAsking(false)
    }
  }

  const doCompare = async () => {
    setComparing(true)
    try {
      const out = await api.compare({ session_id: 'demo-session', query, stream: false, show_retrieval: true })
      setCompare(out)
      setAgentAnswer(null)
    } catch (err: any) {
      setBanner({ tone: 'error', text: `对比失败：${err.message}` })
    } finally {
      setComparing(false)
    }
  }

  const runAgent = async () => {
    setAsking(true)
    try {
      const out = await api.agent({ session_id: 'demo-session', query, stream: false, use_rag: true, show_retrieval: true })
      setAgentAnswer(out)
      setAnswer(null)
      setCompare(null)
    } catch (err: any) {
      setBanner({ tone: 'error', text: `Agent失败：${err.message}` })
    } finally {
      setAsking(false)
    }
  }

  const deleteDocument = async (docId: string) => {
    setDeletingId(docId)
    try {
      await api.deleteDocument(docId)
      setBanner({ tone: 'success', text: `已删除文档 ${docId}` })
      await refreshAll()
    } catch (err: any) {
      setBanner({ tone: 'error', text: `删除失败：${err.message}` })
    } finally {
      setDeletingId(null)
    }
  }

  useEffect(() => {
    refreshAll()
  }, [baseUrl])

  return (
    <div className="layout">
      <header className="topbar">
        <div>
          <h1>小说型 RAG 对比演示系统</h1>
          <p>导入你的小说全文，直接对比「不开 RAG」与「开 RAG」回答差异。</p>
        </div>
        <div className="top-controls">
          <label>API Base URL</label>
          <input value={baseUrl} onChange={e => setBaseUrl(e.target.value)} />
          <button disabled={refreshing} onClick={refreshAll}>{refreshing ? '刷新中...' : '刷新'}</button>
          <select value={mode} onChange={e => setMode(e.target.value as any)}>
            <option value="ask">普通问答</option>
            <option value="rag">RAG问答</option>
            <option value="compare">RAG对比</option>
            <option value="agent">Agent任务</option>
          </select>
        </div>
      </header>

      {banner && <StatusBanner tone={banner.tone} text={banner.text} />}

      <main className="content-grid">
        <div className="left-column">
          <KnowledgeIngestPanel loading={ingesting} onIngest={ingest} result={ingestResult} />
          <SystemStatusPanel stats={stats} system={system} refreshing={refreshing} onRefresh={refreshAll} />
          <DocumentsTable docs={docs} deletingId={deletingId} onDelete={deleteDocument} />
        </div>

        <div className="right-column">
          <AskPanel
            query={query}
            setQuery={setQuery}
            useRag={mode === 'rag'}
            setUseRag={setUseRag}
            showRetrieval={showRetrieval}
            setShowRetrieval={setShowRetrieval}
            asking={asking}
            answer={answer}
            onAsk={mode === 'agent' ? runAgent : async () => {
              if (mode === 'ask') {
                setUseRag(false)
                await api.ask({ session_id: 'demo-session', query, stream: false, use_rag: false, show_retrieval: false }).then(setAnswer)
              } else if (mode === 'rag') {
                setUseRag(true)
                await ask()
              } else {
                await doCompare()
              }
            }}
          />
          <ComparePanel comparing={comparing} compare={compare} onCompare={doCompare} />
          {agentAnswer && <section className="card"><h3>Agent结果</h3><p>{agentAnswer.answer}</p><pre>{JSON.stringify(agentAnswer.metadata, null, 2)}</pre></section>}
        </div>
      </main>
    </div>
  )
}
