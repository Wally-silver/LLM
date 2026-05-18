import { useState } from 'react'
import type { IngestResponse } from '../types'

type Props = {
  loading: boolean
  onIngest: (payload: { source_type: string; source_value: string; recursive: boolean; overwrite: boolean }) => Promise<void>
  onUpload?: (file: File) => Promise<void>
  result: IngestResponse | null
}

export function KnowledgeIngestPanel({ loading, onIngest, onUpload, result }: Props) {
  const [sourceType, setSourceType] = useState('directory')
  const [sourceValue, setSourceValue] = useState('data/knowledge_base')
  const [inlineText, setInlineText] = useState('')

  const submit = async () => {
    await onIngest({
      source_type: sourceType,
      source_value: sourceType === 'inline' ? inlineText : sourceValue,
      recursive: true,
      overwrite: true,
    })
  }

  return (
    <section className="card">
      <h3>知识库导入</h3>
      <select value={sourceType} onChange={e => setSourceType(e.target.value)}>
        {['directory', 'file', 'url', 'inline', 'json', 'jsonl', 'csv'].map(x => <option key={x} value={x}>{x}</option>)}
      </select>
      {sourceType === 'inline' ? (
        <textarea rows={6} value={inlineText} onChange={e => setInlineText(e.target.value)} placeholder="粘贴小说文本" />
      ) : (
        <input value={sourceValue} onChange={e => setSourceValue(e.target.value)} placeholder="输入目录/文件路径或 URL" />
      )}
      <button disabled={loading} onClick={submit}>{loading ? '导入中...' : '导入文档'}</button>
      <input type="file" onChange={async e=>{const f=e.target.files?.[0]; if(f&&onUpload) await onUpload(f)}} />
      {result && (
        <div className="result-box">
          <p>inserted={result.inserted} skipped={result.skipped} total={result.total_docs}</p>
          {result.errors.length > 0 && <pre>{JSON.stringify(result.errors, null, 2)}</pre>}
        </div>
      )}
    </section>
  )
}
