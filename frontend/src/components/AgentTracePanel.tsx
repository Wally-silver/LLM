import { useState } from 'react'
import type { AgentResponse } from '../types'

export function AgentTracePanel({ agent }: { agent: AgentResponse }) {
  const [open, setOpen] = useState(false)
  const steps = agent.metadata?.plan?.steps ?? []
  const history = agent.metadata?.final_state?.history ?? []
  return (
    <section className="card">
      <h3>Agent执行轨迹</h3>
      <p>{agent.answer}</p>
      <h4>Plan Steps</h4>
      {steps.length === 0 ? <p>无计划步骤</p> : (
        <ul>
          {steps.map((s: any, i: number) => <li key={i}>#{s.id ?? i + 1} {s.action} - {s.description}</li>)}
        </ul>
      )}
      <h4>History</h4>
      {history.length === 0 ? <p>无执行历史</p> : history.map((h: any, i: number) => (
        <article key={i} className="hit">
          <div><b>action:</b> {h.step?.action ?? '-'}</div>
          <div><b>result:</b> {typeof h.result?.output?.result === 'string' ? h.result.output.result : JSON.stringify(h.result?.output?.result ?? h.io?.output?.result ?? {})}</div>
          <div><b>critic.score:</b> {h.critic?.score ?? '-'}</div>
          <div><b>transition_decision:</b> {h.transition_decision ?? '-'}</div>
        </article>
      ))}
      <details open={open} onToggle={(e) => setOpen((e.target as HTMLDetailsElement).open)}>
        <summary>{open ? '收起原始JSON' : '展开原始JSON'}</summary>
        <pre>{JSON.stringify(agent.metadata, null, 2)}</pre>
      </details>
    </section>
  )
}
