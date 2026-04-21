from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class TaskOut(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    status: str
    error_message: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
