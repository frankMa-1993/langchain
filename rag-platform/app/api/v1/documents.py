import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import DbSession, get_app_settings, optional_api_key, rate_limit
from app.config import Settings
from app.core.errors import ErrorCode
from app.models.orm import Document, KnowledgeBase
from app.schemas.common import Paginated
from app.schemas.document import DocumentOut, DocumentUploadResponse
from app.services.document_service import (
    DocumentServiceError,
    delete_document,
    enqueue_ingest,
    reindex_document,
    save_upload,
)
from app.services.qdrant_store import QdrantStore

router = APIRouter(dependencies=[Depends(optional_api_key), Depends(rate_limit)])


@router.post("/knowledge-bases/{kb_id}/documents", response_model=DocumentUploadResponse, status_code=202)
async def upload_document(
    kb_id: uuid.UUID,
    db: DbSession,
    file: UploadFile = File(...),
    settings: Settings = Depends(get_app_settings),
) -> DocumentUploadResponse:
    try:
        doc, task = save_upload(db, kb_id, file, settings)
    except DocumentServiceError as e:
        raise HTTPException(
            status_code=_status_for_error(e.code),
            detail={"code": e.code.value, "message": e.message, "detail": e.detail},
        ) from e
    await enqueue_ingest(doc.id, settings)
    return DocumentUploadResponse(document_id=doc.id, task_id=task.id)


@router.get("/knowledge-bases/{kb_id}/documents", response_model=Paginated[DocumentOut])
def list_documents(
    kb_id: uuid.UUID,
    db: DbSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
) -> Paginated[DocumentOut]:
    if not db.get(KnowledgeBase, kb_id):
        raise HTTPException(status_code=404, detail={"code": ErrorCode.NOT_FOUND, "message": "KB not found", "detail": {}})
    q = db.query(Document).filter(Document.kb_id == kb_id)
    total = q.count()
    items = (
        q.order_by(Document.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return Paginated(items=items, total=total, page=page, page_size=page_size)


@router.get("/documents/{document_id}", response_model=DocumentOut)
def get_document(document_id: uuid.UUID, db: DbSession) -> Document:
    doc = db.get(Document, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail={"code": ErrorCode.NOT_FOUND, "message": "Not found", "detail": {}})
    return doc


@router.delete("/documents/{document_id}", status_code=204)
def remove_document(
    document_id: uuid.UUID,
    db: DbSession,
    settings: Settings = Depends(get_app_settings),
) -> None:
    try:
        delete_document(db, document_id, QdrantStore(settings) if settings.semantic_search_active else None)
    except DocumentServiceError as e:
        raise HTTPException(
            status_code=404,
            detail={"code": e.code.value, "message": e.message, "detail": e.detail},
        ) from e


@router.post("/documents/{document_id}/reindex", status_code=202)
async def reindex(
    document_id: uuid.UUID,
    db: DbSession,
    settings: Settings = Depends(get_app_settings),
) -> DocumentUploadResponse:
    try:
        task = reindex_document(db, document_id)
    except DocumentServiceError as e:
        raise HTTPException(
            status_code=404,
            detail={"code": e.code.value, "message": e.message, "detail": e.detail},
        ) from e
    await enqueue_ingest(document_id, settings)
    return DocumentUploadResponse(document_id=document_id, task_id=task.id)


def _status_for_error(code: ErrorCode) -> int:
    if code == ErrorCode.NOT_FOUND:
        return 404
    if code == ErrorCode.UNSUPPORTED_MEDIA:
        return 415
    if code == ErrorCode.DOC_TOO_LARGE:
        return 413
    return 400
