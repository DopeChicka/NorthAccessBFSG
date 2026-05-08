from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import ReviewItem, ReviewItemStatus, ReviewPriority, ReviewSubjectType
from app.services.review_service import (
    ReviewItemNotFoundError,
    create_review_item,
    get_review_item,
    list_review_items,
    update_review_item_status,
)

router = APIRouter(prefix="/review", tags=["review"])


class ReviewItemCreateRequest(BaseModel):
    subject_type: ReviewSubjectType
    subject_id: str
    reason_code: str
    priority: ReviewPriority = ReviewPriority.medium
    notes: str | None = None
    reviewer: str | None = None
    evidence: dict[str, Any] | None = None


class ReviewItemUpdateRequest(BaseModel):
    status: ReviewItemStatus
    notes: str | None = None
    reviewer: str | None = None
    evidence: dict[str, Any] | None = None


@router.get("/items")
def list_items(
    status_filter: ReviewItemStatus | None = Query(default=None, alias="status"),
    subject_type: ReviewSubjectType | None = None,
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    items = list_review_items(
        db,
        status=status_filter,
        subject_type=subject_type,
    )
    return [_serialize_review_item(item) for item in items]


@router.get("/items/{review_item_id}")
def get_item(review_item_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        item = get_review_item(db, review_item_id)
    except ReviewItemNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Review item not found",
        ) from exc
    return _serialize_review_item(item)


@router.post("/items")
def create_item(
    request: ReviewItemCreateRequest, db: Session = Depends(get_db)
) -> dict[str, Any]:
    item = create_review_item(
        db,
        subject_type=request.subject_type,
        subject_id=request.subject_id,
        reason_code=request.reason_code,
        priority=request.priority,
        notes=request.notes,
        reviewer=request.reviewer,
        evidence=request.evidence,
    )
    return _serialize_review_item(item)


@router.patch("/items/{review_item_id}")
def update_item(
    review_item_id: str,
    request: ReviewItemUpdateRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        item = update_review_item_status(
            db,
            review_item_id,
            status=request.status,
            notes=request.notes,
            reviewer=request.reviewer,
            evidence=request.evidence,
        )
    except ReviewItemNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Review item not found",
        ) from exc
    return _serialize_review_item(item)


def _serialize_review_item(item: ReviewItem) -> dict[str, Any]:
    return {
        "id": item.id,
        "subject_type": item.subject_type.value,
        "subject_id": item.subject_id,
        "status": item.status.value,
        "reason_code": item.reason_code,
        "priority": item.priority.value,
        "notes": item.notes,
        "reviewer": item.reviewer,
        "evidence": item.evidence,
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
        "reviewed_at": item.reviewed_at.isoformat() if item.reviewed_at else None,
    }
