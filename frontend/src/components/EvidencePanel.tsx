import type { ChatMessage, Citation, RetrievedHit, RetrievalMetrics } from '../types'

export function RetrievalMetricsCard({ metrics }: { metrics?: RetrievalMetrics }) { if (!metrics) return null; return <section className="card mini"><h4>Retrieval Metrics</h4><div className="metrics-grid"><div>embedding {metrics.embedding_latency_ms}ms</div><div>vector {metrics.vector_search_latency_ms}ms</div><div>rerank {metrics.rerank_latency_ms}ms</div><div>total {metrics.total_retrieval_latency_ms}ms</div></div></section> }
export function RetrievedDocsList({ docs }: { docs?: RetrievedHit[] }) { if (!docs?.length) return null; return <section className="card mini"><h4>Retrieved Docs</h4>{docs.map((d,i)=><details key={i}><summary>{d.title||d.doc_id} ({d.score?.toFixed?.(3) ?? '-'})</summary><p>{d.snippet}</p></details>)}</section> }
export function CitationsList({ citations }: { citations?: Citation[] }) { if (!citations?.length) return null; return <section className="card mini"><h4>Citations</h4>{citations.map((c,i)=><article className="hit" key={i}><b>{c.title||'citation'}</b><p>{c.snippet||'-'}</p></article>)}</section> }
export function UsedToolsCard({ tools }: { tools?: string[] }) { if (!tools?.length) return null; return <section className="card mini"><h4>Used Tools</h4><div>{tools.map(t=><span className="tag" key={t}>{t}</span>)}</div></section> }
export function KGPathsCard({ kg }: { kg?: any[] }) { if (!kg?.length) return null; return <section className="card mini"><h4>KG Paths</h4><pre>{JSON.stringify(kg, null, 2)}</pre></section> }

export function AgentTraceCard({ trace, tools }: { trace?: any; tools?: string[] }) {
  if (!trace || typeof trace !== 'object') return null
  const h = Array.isArray((trace as any).history) ? (trace as any).history : []
  const completed = Array.isArray((trace as any).completed_steps) ? (trace as any).completed_steps.length : 0
  const retries = h.filter((x:any)=>x?.transition_decision==='retry').length
  const replans = h.filter((x:any)=>x?.transition_decision==='replan').length
  const scores = h.map((x:any)=>Number(x?.critic?.score)).filter((x:number)=>!Number.isNaN(x))
  const avg = scores.length ? (scores.reduce((a:number,b:number)=>a+b,0)/scores.length).toFixed(2) : '-'
  return <section className="card mini"><h4>Agent Trace</h4><div>steps:{h.length} completed:{completed} retry:{retries} replan:{replans} critic_avg:{avg}</div>{tools?.length ? <div>{tools.map(t=><span className='tag' key={t}>{t}</span>)}</div> : null}{h.map((x:any,i:number)=><article className='hit' key={i}><b>step {x?.step?.id ?? i+1}</b> {x?.step?.action ?? '-'}<div>result: {typeof x?.result === 'string' ? x.result : JSON.stringify(x?.result ?? x?.io?.output?.result ?? {}).slice(0,120)}</div><div>critic: {x?.critic?.score ?? '-'} / decision: {x?.transition_decision ?? '-'}</div></article>)}<details><summary>原始 JSON</summary><pre>{JSON.stringify(trace, null, 2)}</pre></details></section>
}

export function EvidencePanel({ message }: { message: ChatMessage | null }) {
  if (!message) return <section className="card"><h3>Evidence</h3><p className="empty-state">选择一条 assistant 消息查看证据面板。</p></section>
  return <div className="evidence-stack"><RetrievalMetricsCard metrics={message.retrieval_metrics} /><RetrievedDocsList docs={message.retrieved_docs} /><CitationsList citations={message.citations} /><KGPathsCard kg={message.kg_paths} /><UsedToolsCard tools={message.used_tools} /><AgentTraceCard trace={message.agent_trace} tools={message.used_tools} /><section className="card mini"><details><summary>Raw JSON</summary><pre>{JSON.stringify(message.raw ?? {}, null, 2)}</pre></details></section></div>
}
