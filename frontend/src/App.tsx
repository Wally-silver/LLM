import { useEffect, useMemo, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import { ApiClient } from './lib/api'
import { DocumentsTable } from './components/DocumentsTable'
import { EvidencePanel } from './components/EvidencePanel'
import { KnowledgeIngestPanel } from './components/KnowledgeIngestPanel'
import { SystemStatusPanel } from './components/SystemStatusPanel'
import { StatusBanner } from './components/StatusBanner'
import type { ChatMessage, ChatMode, ChatSession, CompareResponse, RAGStats, SystemStatus } from './types'

const KEY = 'novel-rag-agent:sessions'
const modes: Array<{ k: ChatMode; label: string }> = [
  { k: 'chat', label: '普通问答' }, { k: 'rag', label: 'RAG问答' }, { k: 'compare', label: 'RAG对比' }, { k: 'agent', label: 'Agent任务' }, { k: 'kg', label: 'KG问答' }, { k: 'graph_rag', label: 'GraphRAG' }
]
const now = () => new Date().toISOString()
const id = () => crypto.randomUUID()
const newSession = (): ChatSession => ({ id: id(), title: 'New Chat', created_at: now(), updated_at: now(), messages: [] })

export function App() {
  const [baseUrl, setBaseUrl] = useState(import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000')
  const api = useMemo(() => new ApiClient(baseUrl), [baseUrl])
  const [sessions, setSessions] = useState<ChatSession[]>([])
  const [activeId, setActiveId] = useState('')
  const [search, setSearch] = useState('')
  const [mode, setMode] = useState<ChatMode>('rag')
  const [query, setQuery] = useState('')
  const [showRetrieval, setShowRetrieval] = useState(true)
  const [loading, setLoading] = useState(false)
  const [selectedMsgId, setSelectedMsgId] = useState<string>('')
  const [banner, setBanner] = useState<{ tone: 'success'|'error'|'info'; text: string } | null>(null)
  const [stats, setStats] = useState<RAGStats | null>(null)
  const [system, setSystem] = useState<SystemStatus | null>(null)
  const [docs, setDocs] = useState<any[]>([])

  useEffect(() => { const raw=localStorage.getItem(KEY); if(raw){const arr=JSON.parse(raw) as ChatSession[]; setSessions(arr); setActiveId(arr[0]?.id||'')} else { const s=newSession(); setSessions([s]); setActiveId(s.id)} }, [])
  useEffect(() => { if (sessions.length) localStorage.setItem(KEY, JSON.stringify(sessions)) }, [sessions])
  const active = sessions.find(s=>s.id===activeId) ?? sessions[0]
  const selected = active?.messages.find(m=>m.id===selectedMsgId) ?? active?.messages.filter(m=>m.role==='assistant').at(-1) ?? null

  const refresh = async()=>{ try{ const [s,d,sys]=await Promise.all([api.getRagStats(), api.getDocuments(), api.getSystemStatus()]); setStats(s); setDocs(d.documents); setSystem(sys)}catch(e:any){setBanner({tone:'error',text:e.message})}}
  useEffect(()=>{refresh()},[baseUrl])

  const patchActive=(fn:(s:ChatSession)=>ChatSession)=> setSessions(prev=>prev.map(s=>s.id===active.id?fn(s):s))
  const append=(m:ChatMessage)=> patchActive(s=> ({...s, title: s.messages.length? s.title : (m.role==='user'?m.content.slice(0,20):s.title), updated_at: now(), messages:[...s.messages,m]}))

  const send = async()=>{
    if(!query.trim()||!active) return
    append({id:id(), role:'user', content:query, created_at:now(), mode})
    setLoading(true)
    try {
      let assistant: ChatMessage
      if(mode==='compare'){
        const r:CompareResponse = await api.compare({session_id:active.id,query,stream:false,show_retrieval:true,use_kg:false})
        assistant = {id:id(), role:'assistant', created_at:now(), mode, content:`**No-RAG**\n${r.no_rag_answer}\n\n**RAG**\n${r.rag_answer}`, retrieved_docs:r.retrieved_docs, retrieval_metrics:r.rag_retrieval_metrics, raw:r}
      } else if(mode==='agent'){
        const r= await api.agent({session_id:active.id,query,stream:false,use_rag:true,show_retrieval:true,use_kg:false})
        assistant = {id:id(), role:'assistant', created_at:now(), mode, content:r.answer, used_tools:r.used_tools, agent_trace:r.metadata?.final_state, raw:r}
      } else if(mode==='kg' || mode==='graph_rag'){
        const use_rag = mode==='graph_rag'
        const r = await api.ask({session_id:active.id,query,stream:false,use_rag,show_retrieval:use_rag,use_kg:true})
        assistant={id:id(), role:'assistant', created_at:now(), mode, content:r.answer, citations:r.citations, retrieved_docs:r.retrieved_docs, retrieval_metrics:r.metadata?.retrieval_metrics, used_tools:r.used_tools, kg_paths:r.kg_hits as any, raw:r}
      } else {
        const use_rag = mode==='rag'
        const r = await api.ask({session_id: use_rag?active.id:`${active.id}:plain`, query, stream:false, use_rag, show_retrieval: use_rag?showRetrieval:false, use_kg:false})
        assistant={id:id(), role:'assistant', created_at:now(), mode, content:r.answer, citations:r.citations, retrieved_docs:r.retrieved_docs, retrieval_metrics:r.metadata?.retrieval_metrics, used_tools:r.used_tools, raw:r}
      }
      append(assistant); setSelectedMsgId(assistant.id); setQuery('')
    } catch(e:any){ setBanner({tone:'error', text:e.message || '请求失败'}) }
    setLoading(false)
  }

  const filtered = sessions.filter(s=>s.title.toLowerCase().includes(search.toLowerCase()))
  return <div className='app3'>
    {banner && <StatusBanner tone={banner.tone} text={banner.text} />}
    <aside className='sidebar'><h2>Novel RAG Agent</h2><button onClick={()=>{const s=newSession(); setSessions([s,...sessions]); setActiveId(s.id)}}>+ New Chat</button><input placeholder='搜索会话' value={search} onChange={e=>setSearch(e.target.value)} />
    {filtered.map(s=><div key={s.id} className={`session ${s.id===activeId?'active':''}`}><button onClick={()=>setActiveId(s.id)}>{s.title}</button><button onClick={()=>{const t=prompt('重命名',s.title); if(t) setSessions(p=>p.map(x=>x.id===s.id?{...x,title:t}:x))}}>✎</button><button onClick={()=>{const next=sessions.filter(x=>x.id!==s.id); setSessions(next); if(activeId===s.id&&next[0])setActiveId(next[0].id)}}>🗑</button></div>)}
    </aside>

    <main className='chat'><header><h3>{active?.title || 'Chat'}</h3><div className='mode'>{modes.map(m=><button key={m.k} className={mode===m.k?'pill on':'pill'} onClick={()=>setMode(m.k)}>{m.label}</button>)}</div></header>
    <section className='stream'>{active?.messages.map(m=><div key={m.id} className={`msg ${m.role}`} onClick={()=>m.role==='assistant'&&setSelectedMsgId(m.id)}><div className='bubble'>{m.role==='assistant'?<ReactMarkdown>{m.content}</ReactMarkdown>:m.content}</div></div>)}{loading&&<div className='typing'>Assistant is typing…</div>}</section>
    <footer><textarea value={query} onChange={e=>setQuery(e.target.value)} onKeyDown={e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault(); send()}}} placeholder='输入问题，Enter发送 / Shift+Enter换行' /><label><input type='checkbox' checked={showRetrieval} onChange={e=>setShowRetrieval(e.target.checked)} />show retrieval</label><button disabled={loading} onClick={send}>发送</button></footer></main>

    <aside className='right'><EvidencePanel message={selected} /><SystemStatusPanel stats={stats} system={system} refreshing={false} onRefresh={refresh} /><KnowledgeIngestPanel loading={false} onIngest={async(p)=>{await api.ingest(p);refresh()}} result={null as any} /><DocumentsTable docs={docs} deletingId={null} onDelete={async(id)=>{await api.deleteDocument(id);refresh()}} /></aside>
  </div>
}
