from __future__ import annotations

import asyncio
import hashlib
import uuid
from pathlib import Path

from langchain_text_splitters import RecursiveCharacterTextSplitter
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.metrics import inc_ingest_completed
from app.database import SessionLocal
from app.models.orm import Chunk, Document, DocumentStatus, IngestTask, TaskStatus
from app.services.model_providers import build_embeddings, health_ping_chat
from app.services.parsing import parse_document
from app.services.qdrant_store import QdrantStore


def _hash_content(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def ingest_document_sync(document_id: str) -> None:
    settings = get_settings()
    db: Session = SessionLocal()
    qdrant = QdrantStore(settings) if settings.semantic_search_active else None
    doc_uuid = uuid.UUID(document_id)

    doc = db.get(Document, doc_uuid)
    if not doc:
        db.close()
        return

    task = (
        db.query(IngestTask)
        .filter(IngestTask.document_id == doc_uuid)
        .order_by(IngestTask.created_at.desc())
        .first()
    )

    try:
        doc.status = DocumentStatus.processing.value
        doc.error_message = None
        if task:
            task.status = TaskStatus.processing.value
            task.error_message = None
        db.commit()

        path = Path(doc.storage_path)
        if not path.exists():
            raise FileNotFoundError("Stored file missing")

        text = parse_document(path)
        doc.char_count = len(text)
        db.commit()

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
        )
        pieces = splitter.split_text(text)
        if not pieces:
            raise ValueError("No text extracted from document")

        if qdrant is not None:
            qdrant.delete_by_document(doc_uuid)
        db.query(Chunk).filter(Chunk.document_id == doc_uuid).delete(synchronize_session=False)
        db.commit()

        embeddings = build_embeddings(settings)

        batch_size = 32
        chunk_rows: list[Chunk] = []
        all_ids: list[str] = []
        all_vectors: list[list[float]] = []
        all_payloads: list[dict] = []

        for idx, piece in enumerate(pieces):
            cid = uuid.uuid4()
            ch = Chunk(
                id=cid,
                kb_id=doc.kb_id,
                document_id=doc.id,
                chunk_index=idx,
                content=piece,
                page=None,
                content_hash=_hash_content(piece),
            )
            chunk_rows.append(ch)

        if embeddings is not None and qdrant is not None:
            for i in range(0, len(chunk_rows), batch_size):
                batch = chunk_rows[i : i + batch_size]
                texts = [c.content for c in batch]
                vectors = embeddings.embed_documents(texts)
                for c, vec in zip(batch, vectors, strict=True):
                    all_ids.append(str(c.id))
                    all_vectors.append(vec)
                    all_payloads.append(
                        {
                            "kb_id": str(doc.kb_id),
                            "document_id": str(doc.id),
                            "chunk_id": str(c.id),
                            "filename": doc.filename,
                        }
                    )

            qdrant.ensure_collection(settings.effective_embedding_dimensions)
            if all_ids:
                qdrant.upsert_points(all_ids, all_vectors, all_payloads)

        for c in chunk_rows:
            db.add(c)

        doc.status = DocumentStatus.ready.value
        if task:
            task.status = TaskStatus.completed.value
        db.commit()
        inc_ingest_completed()
    except Exception as e:
        db.rollback()
        doc = db.get(Document, doc_uuid)
        if doc:
            doc.status = DocumentStatus.failed.value
            doc.error_message = str(e)[:2000]
        if task:
            t = db.get(IngestTask, task.id)
            if t:
                t.status = TaskStatus.failed.value
                t.error_message = str(e)[:2000]
        db.commit()
        raise
    finally:
        db.close()


async def process_document(ctx: dict, document_id: str) -> None:
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, ingest_document_sync, document_id)


def health_ping_llm() -> bool:
    return health_ping_chat()
