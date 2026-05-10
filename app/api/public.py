from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, model_validator

from app.core.config import settings
from app.services.public_quick_check_service import (
    QuickCheckValidationError,
    run_public_quick_check,
)

router = APIRouter(prefix="/public", tags=["public"])


class QuickCheckRequest(BaseModel):
    url: str | None = None
    domain: str | None = None

    @model_validator(mode="after")
    def validate_input(self) -> "QuickCheckRequest":
        if self.url and self.url.strip():
            return self
        if self.domain and self.domain.strip():
            return self
        raise ValueError("Either url or domain must be provided")


@router.post("/quick-check")
def quick_check(request: QuickCheckRequest) -> dict[str, object]:
    try:
        return run_public_quick_check(
            url=request.url,
            domain=request.domain,
            timeout_seconds=settings.public_quick_check_timeout_seconds,
            user_agent=settings.public_quick_check_user_agent,
            max_body_bytes=settings.public_quick_check_max_body_bytes,
        )
    except QuickCheckValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
