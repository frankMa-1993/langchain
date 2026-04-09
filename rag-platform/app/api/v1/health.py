from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_app_settings, get_db
from app.config import Settings
from app.core.metrics import snapshot
from app.services.model_providers import health_ping_chat
from app.services.qdrant_store import QdrantStore

router = APIRouter()


@router.get("/health")
def liveness() -> dict:
    return {"status": "ok"}


@router.get("/metrics")
def metrics() -> dict:
    return snapshot()


@router.get("/health/ready")
def readiness(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
) -> dict:
    checks: dict[str, str] = {}

    try:
        db.execute(text("SELECT 1"))
        checks["postgres"] = "ok"
    except Exception as e:
        checks["postgres"] = f"error: {e}"

    if not settings.redis_url.strip():
        checks["redis"] = "disabled"
    else:
        try:
            from redis import Redis

            r = Redis.from_url(settings.redis_url)
            r.ping()
            checks["redis"] = "ok"
        except Exception as e:
            checks["redis"] = f"error: {e}"

    if not settings.semantic_search_active:
        checks["qdrant"] = "disabled"
    else:
        try:
            store = QdrantStore(settings)
            store.client.get_collections()
            checks["qdrant"] = "ok"
        except Exception as e:
            checks["qdrant"] = f"error: {e}"

    checks["llm"] = "ok" if health_ping_chat() else "degraded"

    # #region agent log - diagnostic info in health response
    diag = {
        "chat_api_key_set": bool(settings.chat_api_key),
        "chat_api_key_preview": settings.chat_api_key[:10] + "..." if settings.chat_api_key else None,
        "chat_model": settings.chat_model,
        "chat_base_url": settings.chat_base_url,
        "openai_api_key_set": bool(settings.openai_api_key),
        "effective_chat_api_key_set": bool(settings.effective_chat_api_key),
        "effective_chat_model": settings.effective_chat_model,
        "effective_chat_base_url": settings.effective_chat_base_url,
        "chat_enabled": settings.chat_enabled,
    }
    # #endregion

    ok = all(v in {"ok", "disabled"} for k, v in checks.items() if k != "llm")
    return {"ready": ok, "checks": checks, "diag": diag}
