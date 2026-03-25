from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Industrial AI Agent"
    redis_url: str = "redis://localhost:6379/0"

    # Memory / Cache
    memory_ttl_seconds: int = 86400
    cache_ttl_seconds: int = 3600
    cache_jitter_seconds: int = 300
    cache_lock_seconds: int = 15

    # RAG
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    rerank_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    chunk_token_size: int = 512
    chunk_overlap: int = 64
    rag_top_k: int = 5

    # LLM
    openai_compatible_base_url: str = "http://localhost:8001/v1"
    openai_api_key: str = "EMPTY"
    llm_model_name: str = "Qwen/Qwen2.5-7B-Instruct"
    llm_timeout_seconds: int = 90
    llm_max_retries: int = 3
    llm_default_max_tokens: int = 1024

    # Datasource
    datasource_max_chars: int = 2_000_000

    # Metrics
    metrics_window_size: int = 1000


settings = Settings()
