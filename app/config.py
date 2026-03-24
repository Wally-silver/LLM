from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Industrial AI Agent"
    redis_url: str = "redis://localhost:6379/0"
    cache_ttl_seconds: int = 3600

    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    rerank_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    chunk_token_size: int = 512
    rag_top_k: int = 5

    openai_compatible_base_url: str = "http://localhost:8001/v1"
    openai_api_key: str = "EMPTY"
    llm_model_name: str = "Qwen/Qwen2.5-7B-Instruct"


settings = Settings()
