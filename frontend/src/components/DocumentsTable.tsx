import type { DocumentInfo } from '../types'
import { EmptyState } from './EmptyState'

type Props = {
  docs: DocumentInfo[]
  deletingId: string | null
  onDelete: (docId: string) => Promise<void>
}

function sourceTag(doc: DocumentInfo): string {
  const value = `${doc.title ?? ''} ${doc.source_value}`.toLowerCase()
  if (value.includes('character')) return 'characters'
  if (value.includes('timeline')) return 'timeline'
  if (value.includes('location')) return 'locations'
  if (value.includes('item')) return 'items'
  return 'story'
}

export function DocumentsTable({ docs, deletingId, onDelete }: Props) {
  return (
    <section className="card">
      <h3>文档列表</h3>
      {docs.length === 0 ? (
        <EmptyState title="还没有文档" description="请先在左上角导入你的小说知识库。" />
      ) : (
        <table>
          <thead>
            <tr><th>标签</th><th>title/doc_id</th><th>source</th><th /></tr>
          </thead>
          <tbody>
            {docs.map(d => (
              <tr key={d.doc_id}>
                <td><span className="tag">{sourceTag(d)}</span></td>
                <td><b>{d.title || d.doc_id}</b><br /><small>{d.doc_id}</small></td>
                <td><small>{d.source_type}: {d.source_value}</small></td>
                <td><button disabled={deletingId === d.doc_id} onClick={() => onDelete(d.doc_id)}>{deletingId === d.doc_id ? '删除中...' : '删除'}</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  )
}
