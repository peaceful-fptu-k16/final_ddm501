from __future__ import annotations

from typing import Annotated

from fastapi import Header, HTTPException, status

from src.utils.config import settings


def require_api_key(x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None) -> None:
    if not settings.api_key:
        return
    if x_api_key != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )
