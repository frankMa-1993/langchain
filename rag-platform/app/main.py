from __future__ import annotations

import sys
sys.stderr.write("[DEBUG-MAIN-TOP] main.py loaded - v3\n")
sys.stderr.flush()

import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.v1 import api_router
from app.api.v1.health import router as health_router
from app.config import get_settings
from app.core.metrics import inc_error, inc_http
from app.database import Base, engine
from app.services.qdrant_store import QdrantStore


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        rid = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = rid
        inc_http()
        try:
            response = await call_next(request)
            if response.status_code >= 500:
                inc_error()
            response.headers["X-Request-ID"] = rid
            return response
        except Exception:
            inc_error()
            raise


@asynccontextmanager
async def lifespan(app: FastAPI):
    import sys
    sys.stderr.write("[DEBUG-MAIN] Starting lifespan...\n")
    sys.stderr.flush()
    settings = get_settings()
    sys.stderr.write(f"[DEBUG-MAIN] After get_settings: chat_enabled={settings.chat_enabled}, effective_chat_api_key_set={bool(settings.effective_chat_api_key)}\n")
    sys.stderr.flush()
    Base.metadata.create_all(bind=engine)
    if settings.semantic_search_active:
        store = QdrantStore(settings)
        try:
            store.ensure_collection(settings.effective_embedding_dimensions)
        except Exception:
            pass
    yield


app = FastAPI(
    title="RAG Platform API",
    description="LangChain + FastAPI RAG: knowledge bases, document ingest, hybrid retrieval, SSE chat.",
    version="1.0.0",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestIDMiddleware)

app.include_router(health_router)
app.include_router(api_router, prefix="/api/v1")


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    rid = getattr(request.state, "request_id", None)
    detail = exc.detail
    if isinstance(detail, dict):
        payload = {**detail, "request_id": rid}
    else:
        payload = {
            "code": "HTTP_ERROR",
            "message": str(detail),
            "detail": {},
            "request_id": rid,
        }
    return JSONResponse(status_code=exc.status_code, content=payload)


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    rid = getattr(request.state, "request_id", None)
    return JSONResponse(
        status_code=422,
        content={
            "code": "VALIDATION_ERROR",
            "message": "Request validation failed",
            "detail": exc.errors(),
            "request_id": rid,
        },
    )
