export type ApiError = {
  message: string
  status?: number
  detail?: unknown
}

export type RAGStats = {
  document_count: number
  source_count: number
  chunk_count: number
  index_ready: boolean
  embedding_model: string
  reranker_model: string
  neo4j_enabled: boolean
  neo4j_connected: boolean
}

export type SystemStatus = {
  redis: { available: boolean; error: string | null }
  neo4j: {
    enabled: boolean
    connected: boolean
    error: string | null
    uri: string
    database: string
  }
}

export type DocumentInfo = {
  doc_id: string
  title?: string
  source_type: string
  source_value: string
  metadata?: Record<string, unknown>
}

export type DocumentsResponse = {
  documents: DocumentInfo[]
}

export type IngestRequest = {
  source_type: string
  source_value: string
  doc_id?: string
  recursive?: boolean
  overwrite?: boolean
}

export type IngestResponse = {
  ok: boolean
  inserted: number
  skipped: number
  total_docs: number
  errors: Array<{ source?: string; error: string }>
  kg_errors?: Array<{ doc_id: string; error: string }>
}

export type RetrievedHit = {
  doc_id: string
  title?: string | null
  source_type?: string | null
  source_value?: string | null
  score?: number | null
  snippet: string
  metadata: Record<string, unknown>
}

export type AskRequest = {
  session_id: string
  query: string
  stream: boolean
  use_rag: boolean
  show_retrieval: boolean
}

export type AskResponse = {
  answer: string
  use_rag: boolean
  rag_context: string
  retrieved_docs: RetrievedHit[]
  kg_hits: string[]
  citations: string[]
  used_tools: string[]
  latency_ms: number
  cache_hit: boolean
  metadata: Record<string, unknown>
}

export type CompareResponse = {
  query: string
  no_rag_answer: string
  rag_answer: string
  rag_context: string
  retrieved_docs: RetrievedHit[]
  kg_hits: string[]
  no_rag_latency_ms: number
  rag_latency_ms: number
  latency_diff_ms: number
}
