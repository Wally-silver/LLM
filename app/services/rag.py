from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from importlib.util import find_spec
from typing import Any


@dataclass
class DocumentChunk:
    doc_id: str
    text: str
    metadata: dict[str, Any]


@dataclass
class RAGSnapshot:
    chunks: list[DocumentChunk]
    index: Any
    emb_matrix: Any


class RAGService:
    def __init__(
        self,
        embedding_model: str,
        rerank_model: str,
        chunk_token_size: int = 512,
        top_k: int = 5,
        chunk_overlap: int = 64,
        embedder=None,
        reranker=None,
    ):
        self.embedding_model = embedding_model
        self.rerank_model = rerank_model
        self.embedder = embedder
        self.reranker = reranker
        self.chunk_token_size = chunk_token_size
        self.chunk_overlap = chunk_overlap
        self.top_k = top_k
        self._snapshot = RAGSnapshot(chunks=[], index=None, emb_matrix=None)
        self._rw_lock = asyncio.Lock()

    def _ensure_models(self):
        if self.embedder is None:
            from sentence_transformers import SentenceTransformer

            self.embedder = SentenceTransformer(self.embedding_model)
        if self.reranker is None:
            from sentence_transformers import CrossEncoder

            self.reranker = CrossEncoder(self.rerank_model)

    @staticmethod
    def query_rewrite(query: str) -> str:
        # 可替换为更强的 rewrite LLM 链路
        return query.strip().replace("这个", "该问题").replace("它", "目标对象")

    def chunk_text(self, text: str, doc_id: str) -> list[DocumentChunk]:
        if not text.strip():
            return []
        overlap = self.chunk_overlap if self.chunk_overlap < self.chunk_token_size else 0
        # 小说类中文文本通常空格较少，优先按段落处理，尽量减少语义切碎
        paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
        space_count = text.count(" ")
        cjk_hint = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
        if paragraphs and cjk_hint > max(40, space_count * 2):
            merged: list[str] = []
            buf = ""
            target_chars = self.chunk_token_size * 2
            step_chars = max(1, target_chars - overlap * 2)
            for p in paragraphs:
                if len(buf) + len(p) + 1 <= target_chars:
                    buf = f"{buf}\n{p}".strip()
                else:
                    if buf:
                        merged.append(buf)
                    buf = p
            if buf:
                merged.append(buf)
            return [
                DocumentChunk(
                    doc_id=doc_id,
                    text=segment,
                    metadata={"start_char": i * step_chars, "chunk_mode": "paragraph"},
                )
                for i, segment in enumerate(merged)
            ]

        if find_spec("tiktoken") is not None:
            import tiktoken

            enc = tiktoken.get_encoding("cl100k_base")
            tokens = enc.encode(text)
            step = max(1, self.chunk_token_size - overlap)
            out: list[DocumentChunk] = []
            for i in range(0, len(tokens), step):
                segment = tokens[i : i + self.chunk_token_size]
                if not segment:
                    break
                decoded = enc.decode(segment)
                out.append(DocumentChunk(doc_id=doc_id, text=decoded, metadata={"start_token": i}))
            return out

        words = text.split()
        step = max(1, self.chunk_token_size - overlap)
        out = []
        for i in range(0, len(words), step):
            chunk_words = words[i : i + self.chunk_token_size]
            if not chunk_words:
                break
            out.append(DocumentChunk(doc_id=doc_id, text=" ".join(chunk_words), metadata={"start_word": i}))
        return out

    def _build_snapshot_sync(self, docs: list[tuple[str, str]]) -> RAGSnapshot:
        self._ensure_models()
        chunks: list[DocumentChunk] = []
        for doc_id, text in docs:
            chunks.extend(self.chunk_text(text, doc_id))
        if not chunks:
            return RAGSnapshot(chunks=[], index=None, emb_matrix=None)

        import numpy as np

        embeddings = self.embedder.encode([c.text for c in chunks], normalize_embeddings=True)
        emb = np.asarray(embeddings, dtype="float32")
        if find_spec("faiss") is not None:
            import faiss

            index = faiss.IndexFlatIP(emb.shape[1])
            index.add(emb)
            return RAGSnapshot(chunks=chunks, index=index, emb_matrix=None)
        return RAGSnapshot(chunks=chunks, index=None, emb_matrix=emb)

    async def build_index(self, docs: list[tuple[str, str]]) -> None:
        """Hot-reloadable index build (atomic snapshot swap)."""
        snapshot = await asyncio.to_thread(self._build_snapshot_sync, docs)
        async with self._rw_lock:
            self._snapshot = snapshot

    async def retrieve(self, query: str, top_k: int | None = None) -> list[DocumentChunk]:
        async with self._rw_lock:
            snapshot = self._snapshot
        if not snapshot.chunks:
            return []

        return await asyncio.to_thread(self._retrieve_sync, snapshot, query, top_k)

    async def retrieve_with_metrics(self, query: str, top_k: int | None = None) -> tuple[list[DocumentChunk], dict]:
        begin = time.perf_counter()
        chunks = await self.retrieve(query, top_k=top_k)
        elapsed = int((time.perf_counter() - begin) * 1000)
        scores = [float(c.metadata.get("rerank_score")) for c in chunks if c.metadata.get("rerank_score") is not None]
        k = top_k or self.top_k
        avg_score = (sum(scores) / len(scores)) if scores else None
        return chunks, {
            "top_k": k,
            "retrieved_count": len(chunks),
            "hit_rate": round((len(chunks) / k), 4) if k else 0.0,
            "avg_score": avg_score,
            "max_score": max(scores) if scores else None,
            "min_score": min(scores) if scores else None,
            "retrieval_latency_ms": elapsed,
            "rerank_latency_ms": 0,
            "total_retrieval_latency_ms": elapsed,
        }

    def _retrieve_sync(self, snapshot: RAGSnapshot, query: str, top_k: int | None) -> list[DocumentChunk]:
        self._ensure_models()
        import numpy as np

        k = top_k or self.top_k
        rewritten = self.query_rewrite(query)
        q = self.embedder.encode([rewritten], normalize_embeddings=True)
        qv = np.asarray(q, dtype="float32")

        if snapshot.index is not None:
            _, indices = snapshot.index.search(qv, k)
            candidates = [snapshot.chunks[i] for i in indices[0] if i >= 0]
        else:
            sims = (snapshot.emb_matrix @ qv[0]).tolist()
            order = sorted(range(len(sims)), key=lambda i: sims[i], reverse=True)[:k]
            candidates = [snapshot.chunks[i] for i in order]

        if not candidates:
            return []
        pairs = [(rewritten, c.text) for c in candidates]
        scores = self.reranker.predict(pairs)
        ranked = sorted(zip(candidates, scores), key=lambda x: x[1], reverse=True)
        out: list[DocumentChunk] = []
        for chunk, score in ranked:
            meta = dict(chunk.metadata)
            meta["rerank_score"] = float(score)
            out.append(DocumentChunk(doc_id=chunk.doc_id, text=chunk.text, metadata=meta))
        return out


    def stats(self) -> dict:
        snapshot = self._snapshot
        return {"chunk_count": len(snapshot.chunks), "indexed": bool(snapshot.chunks)}
