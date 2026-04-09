import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import DbSession, get_app_settings, optional_api_key, rate_limit
from app.config import Settings
from app.core.errors import ErrorCode
from app.models.orm import Document, KnowledgeBase
from app.schemas.common import Paginated
from app.schemas.knowledge_base import KnowledgeBaseCreate, KnowledgeBaseOut
from app.services.qdrant_store import QdrantStore

router = APIRouter(dependencies=[Depends(optional_api_key), Depends(rate_limit)])


@router.post("", response_model=KnowledgeBaseOut, status_code=201)
def create_kb(body: KnowledgeBaseCreate, db: DbSession) -> KnowledgeBase:
    kb = KnowledgeBase(name=body.name, description=body.description)
    db.add(kb)
    db.commit()
    db.refresh(kb)
    return kb


@router.get("", response_model=Paginated[KnowledgeBaseOut])
def list_kbs(
    db: DbSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
) -> Paginated[KnowledgeBaseOut]:
    q = db.query(KnowledgeBase)
    total = q.count()
    items = (
        q.order_by(KnowledgeBase.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return Paginated(items=items, total=total, page=page, page_size=page_size)


@router.get("/{kb_id}", response_model=KnowledgeBaseOut)
def get_kb(kb_id: uuid.UUID, db: DbSession) -> KnowledgeBase:
    kb = db.get(KnowledgeBase, kb_id)
    if not kb:
        raise HTTPException(status_code=404, detail={"code": ErrorCode.NOT_FOUND, "message": "Not found", "detail": {}})
    return kb


@router.delete("/{kb_id}", status_code=204)
def delete_kb(
    kb_id: uuid.UUID,
    db: DbSession,
    settings: Settings = Depends(get_app_settings),
) -> None:
    kb = db.get(KnowledgeBase, kb_id)
    if not kb:
        raise HTTPException(status_code=404, detail={"code": ErrorCode.NOT_FOUND, "message": "Not found", "detail": {}})

    if settings.semantic_search_active:
        store = QdrantStore(settings)
        try:
            store.delete_by_kb(kb_id)
        except Exception:
            pass

    docs = db.query(Document).filter(Document.kb_id == kb_id).all()
    for d in docs:
        from pathlib import Path

        p = Path(d.storage_path)
        if p.exists():
            try:
                p.unlink()
            except OSError:
                pass

    db.delete(kb)
    db.commit()
