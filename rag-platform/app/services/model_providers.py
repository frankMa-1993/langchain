from __future__ import annotations

import httpx
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from app.config import Settings, get_settings


def build_chat_model(
    settings: Settings | None = None,
    *,
    streaming: bool,
    temperature: float = 0.2,
) -> ChatOpenAI | None:
    settings = settings or get_settings()
    # #region agent log - build_chat_model entry
    print(f"[DEBUG] build_chat_model: chat_enabled={settings.chat_enabled}")
    print(f"[DEBUG] effective_chat_api_key_set={bool(settings.effective_chat_api_key)}, model={settings.effective_chat_model}")
    # #endregion
    if not settings.chat_enabled:
        # #region agent log - chat disabled
        print("[DEBUG] Chat not enabled, returning None")
        # #endregion
        return None
    # #region agent log - creating ChatOpenAI
    print(f"[DEBUG] Creating ChatOpenAI with model={settings.effective_chat_model}")
    # #endregion
    return ChatOpenAI(
        model=settings.effective_chat_model,
        api_key=settings.effective_chat_api_key or None,
        base_url=settings.effective_chat_base_url or None,
        streaming=streaming,
        temperature=temperature,
    )


def build_embeddings(settings: Settings | None = None) -> OpenAIEmbeddings | None:
    settings = settings or get_settings()
    if not settings.semantic_search_active:
        return None
    return OpenAIEmbeddings(
        model=settings.effective_embedding_model,
        api_key=settings.effective_embedding_api_key or None,
        base_url=settings.effective_embedding_base_url or None,
    )


def health_ping_chat() -> bool:
    settings = get_settings()
    if not settings.chat_enabled:
        return False
    try:
        base = (settings.effective_chat_base_url or "https://api.openai.com/v1").rstrip("/")
        with httpx.Client(timeout=5.0) as client:
            r = client.get(f"{base}/models", headers={"Authorization": f"Bearer {settings.effective_chat_api_key}"})
        return r.status_code < 500
    except Exception:
        return False
