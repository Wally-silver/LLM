from dataclasses import dataclass



@dataclass
class DocumentChunk:
    doc_id: str
    text: str


class RAGService:
    def __init__(
        self,
        embedding_model: str,
        rerank_model: str,
        chunk_token_size: int = 512,
        top_k: int = 5,
        embedder=None,
        reranker=None,
    ):
        self.embedding_model = embedding_model
        self.rerank_model = rerank_model
        self.embedder = embedder
        self.reranker = reranker
        self.chunk_token_size = chunk_token_size
        self.top_k = top_k
        self.chunks: list[DocumentChunk] = []
        self.index = None
        self._emb_matrix = None

    def _ensure_models(self):
        if self.embedder is None:
            from sentence_transformers import SentenceTransformer

            self.embedder = SentenceTransformer(self.embedding_model)
        if self.reranker is None:
            from sentence_transformers import CrossEncoder

            self.reranker = CrossEncoder(self.rerank_model)

    @staticmethod
    def query_rewrite(query: str) -> str:
        return query.strip().replace("这个", "该问题").replace("它", "目标对象")

    def chunk_text(self, text: str, doc_id: str) -> list[DocumentChunk]:
        words = text.split()
        if not words:
            return []
        stride = self.chunk_token_size
        chunks = []
        for i in range(0, len(words), stride):
            chunk = " ".join(words[i : i + stride])
            chunks.append(DocumentChunk(doc_id=doc_id, text=chunk))
        return chunks

    def build_index(self, docs: list[tuple[str, str]]) -> None:
        all_chunks: list[DocumentChunk] = []
        for doc_id, text in docs:
            all_chunks.extend(self.chunk_text(text, doc_id))
        if not all_chunks:
            self.index = None
            self._emb_matrix = None
            self.chunks = []
            return

        self._ensure_models()
        embeddings = self.embedder.encode([c.text for c in all_chunks], normalize_embeddings=True)
        import numpy as np

        emb = np.asarray(embeddings, dtype="float32")

        # Prefer FAISS if installed; fallback to numpy similarity for lightweight environments.
        from importlib.util import find_spec

        if find_spec("faiss") is not None:
            import faiss

            self.index = faiss.IndexFlatIP(emb.shape[1])
            self.index.add(emb)
            self._emb_matrix = None
        else:
            self.index = None
            self._emb_matrix = emb

        self.chunks = all_chunks

    def retrieve(self, query: str, top_k: int | None = None) -> list[DocumentChunk]:
        if (self.index is None and self._emb_matrix is None) or not self.chunks:
            return []
        self._ensure_models()
        k = top_k or self.top_k
        rewritten = self.query_rewrite(query)
        q = self.embedder.encode([rewritten], normalize_embeddings=True)
        import numpy as np

        qv = np.asarray(q, dtype="float32")

        if self.index is not None:
            _, indices = self.index.search(qv, k)
            candidates = [self.chunks[i] for i in indices[0] if i >= 0]
        else:
            sims = (self._emb_matrix @ qv[0]).tolist()
            order = sorted(range(len(sims)), key=lambda i: sims[i], reverse=True)[:k]
            candidates = [self.chunks[i] for i in order]

        if not candidates:
            return []

        pairs = [(rewritten, c.text) for c in candidates]
        scores = self.reranker.predict(pairs)
        ranked = sorted(zip(candidates, scores), key=lambda x: x[1], reverse=True)
        return [item[0] for item in ranked]
