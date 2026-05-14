import { useState } from 'react'
import type { AgentResponse } from '../types'

export function AgentTracePanel({ agent }: { agent: AgentResponse }) {
  const [open, setOpen] = useState(false)
  const steps = agent.metadata?.plan?.steps ?? []
  const history = agent.metadata?.final_state?.history ?? []
  const retries = history.filter((h: any) => h.transition_decision === 'retry').length
  const replans = history.filter((h: any) => h.transition_decision === 'replan').length
  const criticScores = history.map((h: any) => Number(h.critic?.score)).filter((x: number) => !Number.isNaN(x))
  const avgCritic = criticScores.length ? (criticScores.reduce((a: number, b: number) => a + b, 0) / criticScores.length) : 0
  return (
    <section className="card">
      <h3>Agent执行轨迹</h3>
      <p>{agent.answer}</p>
      <div className="metrics-grid">
        <div>总step数: <b>{steps.length}</b></div>
        <div>retry次数: <b>{retries}</b></div>
        <div>replan次数: <b>{replans}</b></div>
        <div>critic平均分: <b>{avgCritic.toFixed(2)}</b></div>
        <div>总耗时: <b>{String((agent.metadata as any)?.duration_ms ?? '-')}ms</b></div>
      </div>
      <h4>Plan Steps</h4>
      {steps.length === 0 ? <p>无计划步骤</p> : (
        <div>
          {steps.map((s: any, i: number) => (
            <article className="hit" key={i}>
              <b>Step {s.id ?? i + 1}: {s.action}</b>
              <p>{s.description || '-'}</p>
              <small>expected_output: {s.expected_output || '-'}</small>
            </article>
          ))}
        </div>
      )}
      <h4>History</h4>
      {history.length === 0 ? <p>无执行历史</p> : history.map((h: any, i: number) => (
        <article key={i} className="hit">
          <div><b>agent:</b> {h.agent ?? 'executor/critic'}</div>
          <div><b>action:</b> {h.step?.action ?? '-'}</div>
          <div><b>输入摘要:</b> {JSON.stringify(h.result?.input ?? h.io?.input ?? {}).slice(0, 180)}</div>
          <div><b>输出摘要:</b> {typeof h.result?.output?.result === 'string' ? h.result.output.result.slice(0, 200) : JSON.stringify(h.result?.output?.result ?? h.io?.output?.result ?? {}).slice(0, 200)}</div>
          <div><b>critic.score:</b> {h.critic?.score ?? '-'}</div>
          <div><b>transition_decision:</b> {h.transition_decision ?? '-'}</div>
          <div><b>retry/replan:</b> {h.transition_decision === 'retry' ? 'retry' : h.transition_decision === 'replan' ? 'replan' : 'none'}</div>
        </article>
      ))}
      <details open={open} onToggle={(e) => setOpen((e.target as HTMLDetailsElement).open)}>
        <summary>{open ? '收起原始JSON' : '展开原始JSON'}</summary>
        <pre>{JSON.stringify(agent.metadata, null, 2)}</pre>
      </details>
    </section>
  )
}
