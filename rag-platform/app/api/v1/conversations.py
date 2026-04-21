from __future__ import annotations

import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import StreamingResponse
from app.api.deps import DbSession, optional_api_key, rate_limit
from app.database import SessionLocal
from app.core.errors import ErrorCode
from app.models.orm import Conversation, Message
from app.schemas.common import Paginated
from app.schemas.conversation import (
    BatchDeleteRequest,
    ConversationCreate,
    ConversationOut,
    MessageCreate,
    MessageOut,
    SourceRef,
    StreamChatRequest,
)
from app.core.metrics import inc_stream
from app.services.rag_service import RAGService

router = APIRouter(dependencies=[Depends(optional_api_key), Depends(rate_limit)])


def _message_out(m: Message) -> MessageOut:
    sources = None
    if m.sources_json:
        raw = json.loads(m.sources_json)
        sources = [SourceRef.model_validate(x) for x in raw]
    return MessageOut(
        id=m.id,
        conversation_id=m.conversation_id,
        role=m.role,
        content=m.content,
        sources=sources,
        created_at=m.created_at,
    )


@router.post("", response_model=ConversationOut, status_code=201)
def create_conversation(body: ConversationCreate, db: DbSession) -> Conversation:
    conv = Conversation(kb_id=body.kb_id, title=body.title)
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return conv


@router.get("", response_model=Paginated[ConversationOut])
def list_conversations(
    db: DbSession,
    kb_id: uuid.UUID | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
) -> Paginated[ConversationOut]:
    q = db.query(Conversation)
    if kb_id is not None:
        q = q.filter(Conversation.kb_id == kb_id)
    total = q.count()
    items = (
        q.order_by(Conversation.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return Paginated(items=items, total=total, page=page, page_size=page_size)


@router.get("/{conversation_id}/messages", response_model=Paginated[MessageOut])
def list_messages(
    conversation_id: uuid.UUID,
    db: DbSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=200),
) -> Paginated[MessageOut]:
    if not db.get(Conversation, conversation_id):
        raise HTTPException(status_code=404, detail={"code": ErrorCode.NOT_FOUND, "message": "Not found", "detail": {}})
    q = db.query(Message).filter(Message.conversation_id == conversation_id)
    total = q.count()
    rows = (
        q.order_by(Message.created_at.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return Paginated(items=[_message_out(m) for m in rows], total=total, page=page, page_size=page_size)


@router.post("/{conversation_id}/messages", response_model=MessageOut, status_code=201)
def create_message_sync(
    conversation_id: uuid.UUID,
    body: MessageCreate,
    db: DbSession,
) -> MessageOut:
    if not db.get(Conversation, conversation_id):
        raise HTTPException(status_code=404, detail={"code": ErrorCode.NOT_FOUND, "message": "Not found", "detail": {}})
    rag = RAGService(db)
    try:
        _, sources = rag.answer_sync(conversation_id, body.content)
    except ValueError:
        raise HTTPException(
            status_code=404,
            detail={"code": ErrorCode.NOT_FOUND, "message": "Conversation not found", "detail": {}},
        ) from None
    last = (
        db.query(Message)
        .filter(Message.conversation_id == conversation_id, Message.role == "assistant")
        .order_by(Message.created_at.desc())
        .first()
    )
    if not last:
        raise HTTPException(status_code=500, detail={"code": ErrorCode.INTERNAL_ERROR, "message": "No reply", "detail": {}})
    return _message_out(last)


@router.post("/{conversation_id}/chat/stream")
async def chat_stream(
    conversation_id: uuid.UUID,
    body: StreamChatRequest,
    db: DbSession,
):
    if not db.get(Conversation, conversation_id):
        raise HTTPException(status_code=404, detail={"code": ErrorCode.NOT_FOUND, "message": "Not found", "detail": {}})

    cid = conversation_id
    content = body.content
    hybrid = body.hybrid
    top_k = body.top_k

    async def event_gen():
        inc_stream()
        stream_db = SessionLocal()
        try:
            rag = RAGService(stream_db)
            async for ev in rag.stream_events(
                cid,
                content,
                hybrid=hybrid,
                top_k=top_k,
            ):
                yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"
        finally:
            stream_db.close()

    return StreamingResponse(event_gen(), media_type="text/event-stream")


@router.delete("/{conversation_id}", status_code=204, response_class=Response)
def delete_conversation(
    conversation_id: uuid.UUID,
    db: DbSession,
) -> Response:
    """Delete a single conversation and its associated messages (cascade)."""
    conv = db.get(Conversation, conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail={"code": ErrorCode.NOT_FOUND, "message": "Conversation not found", "detail": {}})
    db.delete(conv)
    db.commit()
    return Response(status_code=204)


@router.post("/batch-delete", status_code=204, response_class=Response)
def batch_delete_conversations(
    body: BatchDeleteRequest,
    db: DbSession,
) -> Response:
    """Delete multiple conversations and their associated messages (cascade)."""
    if not body.ids:
        return Response(status_code=204)
    # Query all conversations that exist
    convs = db.query(Conversation).filter(Conversation.id.in_(body.ids)).all()
    existing_ids = {c.id for c in convs}
    # If some IDs don't exist, still delete the existing ones (idempotent)
    for conv in convs:
        db.delete(conv)
    db.commit()
    return Response(status_code=204)
