import type {
  AskRequest,
  AskResponse,
  CompareResponse,
  DocumentsResponse,
  IngestRequest,
  IngestResponse,
  RAGStats,
  SystemStatus,
} from '../types'

export class ApiClient {
  constructor(private baseUrl: string) {}

  setBaseUrl(next: string) {
    this.baseUrl = next
  }

  private async request<T>(path: string, init?: RequestInit): Promise<T> {
    const res = await fetch(`${this.baseUrl}${path}`, {
      ...init,
      headers: {
        'Content-Type': 'application/json',
        ...(init?.headers ?? {}),
      },
    })

    const contentType = res.headers.get('content-type') ?? ''
    const payload = contentType.includes('application/json') ? await res.json() : await res.text()

    if (!res.ok) {
      const message = typeof payload === 'string' ? payload : payload?.detail?.message || payload?.detail || 'Request failed'
      throw { message, status: res.status, detail: payload }
    }

    return payload as T
  }

  get<T>(path: string) {
    return this.request<T>(path)
  }

  post<T>(path: string, body: unknown) {
    return this.request<T>(path, { method: 'POST', body: JSON.stringify(body) })
  }

  delete<T>(path: string) {
    return this.request<T>(path, { method: 'DELETE' })
  }

  getRagStats() {
    return this.get<RAGStats>('/rag/stats')
  }

  getSystemStatus() {
    return this.get<SystemStatus>('/system/status')
  }

  getDocuments() {
    return this.get<DocumentsResponse>('/documents')
  }

  ingest(payload: IngestRequest) {
    return this.post<IngestResponse>('/datasources/ingest', payload)
  }

  ask(payload: AskRequest) {
    return this.post<AskResponse>('/ask', payload)
  }

  compare(payload: Omit<AskRequest, 'use_rag'>) {
    return this.post<CompareResponse>('/ask/compare', payload)
  }

  deleteDocument(docId: string) {
    return this.delete<{ ok: boolean; deleted_doc_id: string }>(`/documents/${docId}`)
  }

  rebuildRag() {
    return this.post<{ ok: boolean; docs: number }>('/rag/rebuild', {})
  }
}
