from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.core.errors import ErrorCode
from app.database import get_db

DbSession = Annotated[Session, Depends(get_db)]


def get_app_settings() -> Settings:
    return get_settings()


def optional_api_key(
    request: Request,
    x_api_key: Annotated[str | None, Header()] = None,
    settings: Settings = Depends(get_app_settings),
) -> None:
    if not settings.api_key:
        return
    if x_api_key != settings.api_key:
        raise HTTPException(
            status_code=401,
            detail={
                "code": ErrorCode.UNAUTHORIZED,
                "message": "Invalid or missing API key",
                "detail": {},
            },
        )


def rate_limit(request: Request, settings: Settings = Depends(get_app_settings)) -> None:
    from app.services.cache import rate_limit_allow

    if settings.rate_limit_per_minute <= 0:
        return
    ip = request.client.host if request.client else "unknown"
    if not rate_limit_allow(ip, settings.rate_limit_per_minute):
        raise HTTPException(
            status_code=429,
            detail={
                "code": ErrorCode.RATE_LIMITED,
                "message": "Too many requests",
                "detail": {},
            },
        )
