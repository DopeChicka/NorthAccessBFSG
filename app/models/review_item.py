from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Enum, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ReviewSubjectType(str, enum.Enum):
    finding = "finding"
    compliance_mapping = "compliance_mapping"
    candidate = "candidate"
    website_probe = "website_probe"


class ReviewItemStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    needs_more_info = "needs_more_info"


class ReviewPriority(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class ReviewItem(Base):
    __tablename__ = "review_items"
    __table_args__ = (
        UniqueConstraint(
            "subject_type",
            "subject_id",
            "reason_code",
            name="uq_review_items_subject_reason",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    subject_type: Mapped[ReviewSubjectType] = mapped_column(
        Enum(ReviewSubjectType, name="review_subject_type"),
        nullable=False,
        index=True,
    )
    subject_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    status: Mapped[ReviewItemStatus] = mapped_column(
        Enum(ReviewItemStatus, name="review_item_status"),
        default=ReviewItemStatus.pending,
        nullable=False,
        index=True,
    )
    reason_code: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    priority: Mapped[ReviewPriority] = mapped_column(
        Enum(ReviewPriority, name="review_priority"),
        default=ReviewPriority.medium,
        nullable=False,
        index=True,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewer: Mapped[str | None] = mapped_column(String(255), nullable=True)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
