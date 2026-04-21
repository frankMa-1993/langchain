from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+psycopg://rag:rag@localhost:5432/rag"
    redis_url: str = "redis://localhost:6379/0"
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "kb_chunks"

    openai_api_key: str = ""
    openai_base_url: str | None = None
    llm_model: str = "gpt-4o-mini"
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536

    # Preferred chat provider configuration. Falls back to the legacy OPENAI_* values.
    chat_api_key: str = ""
    chat_base_url: str | None = None
    chat_model: str = ""

    # Optional semantic retrieval provider. Disabled by default for maximum stability.
    semantic_search_enabled: bool = False
    semantic_api_key: str = ""
    semantic_base_url: str | None = None
    semantic_model: str = ""
    semantic_dimensions: int = 0

    chunk_size: int = 1000
    chunk_overlap: int = 200
    max_upload_mb: int = 50
    upload_dir: str = "./uploads"

    api_key: str | None = None
    rate_limit_per_minute: int = 60

    # Retrieval defaults
    semantic_k: int = 12
    keyword_k: int = 12
    final_top_k: int = 6
    chat_history_max_messages: int = 20

    @property
    def effective_chat_api_key(self) -> str:
        return self.chat_api_key or self.openai_api_key

    @property
    def effective_chat_base_url(self) -> str | None:
        return self.chat_base_url or self.openai_base_url

    @property
    def effective_chat_model(self) -> str:
        return self.chat_model or self.llm_model

    @property
    def chat_enabled(self) -> bool:
        return bool(self.effective_chat_api_key and self.effective_chat_model)

    @property
    def effective_embedding_api_key(self) -> str:
        return self.semantic_api_key or self.openai_api_key

    @property
    def effective_embedding_base_url(self) -> str | None:
        return self.semantic_base_url or self.openai_base_url

    @property
    def effective_embedding_model(self) -> str:
        return self.semantic_model or self.embedding_model

    @property
    def effective_embedding_dimensions(self) -> int:
        return self.semantic_dimensions or self.embedding_dimensions

    @property
    def semantic_search_active(self) -> bool:
        return self.semantic_search_enabled and bool(self.effective_embedding_model)


@lru_cache
def get_settings() -> Settings:
    import os, sys
    env_chat_key = os.getenv('CHAT_API_KEY', 'NOT_SET')[:10] if os.getenv('CHAT_API_KEY') else 'NOT_SET'
    env_chat_model = os.getenv('CHAT_MODEL', 'NOT_SET')
    sys.stderr.write(f"[DEBUG-CONFIG] Raw env CHAT_API_KEY={env_chat_key}..., CHAT_MODEL={env_chat_model}\n")
    sys.stderr.flush()
    
    s = Settings()
    # #region agent log - config loaded
    chat_key_preview = s.chat_api_key[:10] if s.chat_api_key else 'EMPTY'
    sys.stderr.write(f"[DEBUG-CONFIG] Settings chat_api_key_preview={chat_key_preview}..., chat_model='{s.chat_model}', chat_enabled={s.chat_enabled}\n")
    sys.stderr.write(f"[DEBUG-CONFIG] effective_chat_api_key_preview={s.effective_chat_api_key[:10] if s.effective_chat_api_key else 'EMPTY'}..., effective_chat_model='{s.effective_chat_model}'\n")
    sys.stderr.flush()
    # #endregion
    return s
