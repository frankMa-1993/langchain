import uuid

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import DbSession, optional_api_key, rate_limit
from app.core.errors import ErrorCode
from app.models.orm import IngestTask
from app.schemas.task import TaskOut

router = APIRouter(dependencies=[Depends(optional_api_key), Depends(rate_limit)])


@router.get("/tasks/{task_id}", response_model=TaskOut)
def get_task(task_id: uuid.UUID, db: DbSession) -> IngestTask:
    t = db.get(IngestTask, task_id)
    if not t:
        raise HTTPException(status_code=404, detail={"code": ErrorCode.NOT_FOUND, "message": "Not found", "detail": {}})
    return t
