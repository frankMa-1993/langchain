import uuid
from datetime import datetime
from pydantic import BaseModel, Field


class ConversationCreate(BaseModel):
    kb_id: uuid.UUID
    title: str | None = Field(default=None, max_length=512)


class ConversationOut(BaseModel):
    id: uuid.UUID
    kb_id: uuid.UUID
    title: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class MessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=32000)


class SourceRef(BaseModel):
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    filename: str
    page: int | None = None
    excerpt: str | None = None


class MessageOut(BaseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    role: str
    content: str
    sources: list[SourceRef] | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class StreamChatRequest(BaseModel):
    content: str = Field(min_length=1, max_length=32000)
    hybrid: bool = True
    top_k: int | None = Field(default=None, ge=1, le=30)


class BatchDeleteRequest(BaseModel):
    ids: list[uuid.UUID] = Field(min_length=1, max_length=100)
