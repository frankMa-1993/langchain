from __future__ import annotations

import asyncio
import uuid
from pathlib import Path

from arq import create_pool
from arq.connections import RedisSettings
from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.core.errors import ErrorCode
from app.models.orm import Document, DocumentStatus, IngestTask, KnowledgeBase, TaskStatus
from app.services.qdrant_store import QdrantStore


ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".text", ".md", ".markdown"}


class DocumentServiceError(Exception):
    def __init__(self, code: ErrorCode, message: str, detail: dict | None = None) -> None:
        self.code = code
        self.message = message
        self.detail = detail or {}
        super().__init__(message)


def ensure_kb(db: Session, kb_id: uuid.UUID) -> KnowledgeBase:
    kb = db.get(KnowledgeBase, kb_id)
    if not kb:
        raise DocumentServiceError(ErrorCode.NOT_FOUND, "Knowledge base not found", {"kb_id": str(kb_id)})
    return kb


async def enqueue_ingest(document_id: uuid.UUID, settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    if not settings.redis_url.strip():
        from app.workers.ingest import ingest_document_sync

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, ingest_document_sync, str(document_id))
        return

    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    try:
        pool = await create_pool(redis_settings)
        try:
            await pool.enqueue_job("process_document", str(document_id))
            return
        finally:
            await pool.close()
    except Exception:
        from app.workers.ingest import ingest_document_sync

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, ingest_document_sync, str(document_id))


def save_upload(
    db: Session,
    kb_id: uuid.UUID,
    file: UploadFile,
    settings: Settings | None = None,
) -> tuple[Document, IngestTask]:
    settings = settings or get_settings()
    ensure_kb(db, kb_id)

    filename = file.filename or "unnamed"
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise DocumentServiceError(
            ErrorCode.UNSUPPORTED_MEDIA,
            f"Unsupported file type: {ext}",
            {"allowed": sorted(ALLOWED_EXTENSIONS)},
        )

    max_bytes = settings.max_upload_mb * 1024 * 1024
    upload_root = Path(settings.upload_dir)
    upload_root.mkdir(parents=True, exist_ok=True)

    doc_id = uuid.uuid4()
    storage_name = f"{doc_id}{ext}"
    dest = upload_root / storage_name

    size = 0
    with dest.open("wb") as out:
        while True:
            chunk = file.file.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            if size > max_bytes:
                dest.unlink(missing_ok=True)
                raise DocumentServiceError(
                    ErrorCode.DOC_TOO_LARGE,
                    "File exceeds maximum upload size",
                    {"max_mb": settings.max_upload_mb},
                )
            out.write(chunk)

    doc = Document(
        id=doc_id,
        kb_id=kb_id,
        filename=filename,
        mime_type=file.content_type,
        status=DocumentStatus.pending.value,
        storage_path=str(dest.resolve()),
    )
    db.add(doc)
    db.flush()

    task = IngestTask(document_id=doc.id, status=TaskStatus.pending.value)
    db.add(task)
    db.commit()
    db.refresh(doc)
    db.refresh(task)
    return doc, task


def delete_document(db: Session, document_id: uuid.UUID, qdrant: QdrantStore | None = None) -> None:
    settings = get_settings()
    doc = db.get(Document, document_id)
    if not doc:
        raise DocumentServiceError(ErrorCode.NOT_FOUND, "Document not found", {"document_id": str(document_id)})

    path = Path(doc.storage_path)
    if qdrant is not None:
        qdrant.delete_by_document(document_id)
    elif settings.semantic_search_active:
        QdrantStore(settings).delete_by_document(document_id)
    db.delete(doc)
    db.commit()
    if path.exists():
        try:
            path.unlink()
        except OSError:
            pass


def reindex_document(db: Session, document_id: uuid.UUID) -> IngestTask:
    doc = db.get(Document, document_id)
    if not doc:
        raise DocumentServiceError(ErrorCode.NOT_FOUND, "Document not found", {"document_id": str(document_id)})

    doc.status = DocumentStatus.pending.value
    doc.error_message = None
    task = IngestTask(document_id=doc.id, status=TaskStatus.pending.value)
    db.add(task)
    db.commit()
    db.refresh(task)
    return task
