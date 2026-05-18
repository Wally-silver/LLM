from app.services.rag import RAGService


def test_chunk_text():
    rag = RAGService(
        embedding_model="sentence-transformers/all-MiniLM-L6-v2",
        rerank_model="cross-encoder/ms-marco-MiniLM-L-6-v2",
        chunk_token_size=3,
        top_k=2,
    )
    chunks = rag.chunk_text("a b c d e f g", "d1")
    assert len(chunks) == 3
    assert chunks[0].text == "a b c"
