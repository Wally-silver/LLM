"""Retrieval-Augmented Generation (RAG) service.

职责：
- 文本 chunk 切分（默认约 512 token 的词粒度近似）
- embedding 编码并构建向量检索索引
- top-k 初筛 + cross-encoder 精排
- query rewrite 预处理
"""

from dataclasses import dataclass


@dataclass
class DocumentChunk:
    """知识块结构。"""

    doc_id: str
    text: str


class RAGService:
    """可独立复用的 RAG 组件。"""

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
        """延迟加载模型，避免应用启动时就拉起大模型占用资源。"""
        if self.embedder is None:
            from sentence_transformers import SentenceTransformer

            self.embedder = SentenceTransformer(self.embedding_model)
        if self.reranker is None:
            from sentence_transformers import CrossEncoder

            self.reranker = CrossEncoder(self.rerank_model)

    @staticmethod
    def query_rewrite(query: str) -> str:
        """轻量 query rewrite，可扩展为 LLM rewrite 或规则库。"""
        return query.strip().replace("这个", "该问题").replace("它", "目标对象")

    def chunk_text(self, text: str, doc_id: str) -> list[DocumentChunk]:
        """按近似 token 长度切块。

        当前用空格分词近似 token 切分，便于演示；
        生产中可替换为 tiktoken / tokenizer 的精确 token 计数切分。
        """
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
        """构建索引：支持 FAISS（优先）与 numpy fallback。"""
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

        # 优先使用 FAISS；缺失时回退为 numpy 点积检索，保证最小可运行。
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
        """检索主流程：rewrite -> 向量召回 -> rerank。"""
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
            # fallback：直接做向量点积并按分值排序。
            sims = (self._emb_matrix @ qv[0]).tolist()
            order = sorted(range(len(sims)), key=lambda i: sims[i], reverse=True)[:k]
            candidates = [self.chunks[i] for i in order]

        if not candidates:
            return []

        pairs = [(rewritten, c.text) for c in candidates]
        scores = self.reranker.predict(pairs)
        ranked = sorted(zip(candidates, scores), key=lambda x: x[1], reverse=True)
        return [item[0] for item in ranked]
