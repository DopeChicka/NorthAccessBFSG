from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class JourneyType(str, enum.Enum):
    homepage = "homepage"
    login = "login"
    shop = "shop"
    cart = "cart"
    checkout = "checkout"
    booking = "booking"
    search = "search"
    contact_form = "contact_form"


class JourneyStatus(str, enum.Enum):
    planned = "planned"
    skipped = "skipped"
    ready = "ready"
    failed = "failed"


class Journey(Base):
    __tablename__ = "journeys"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    scan_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("scans.id", ondelete="CASCADE"), nullable=False, index=True
    )
    journey_type: Mapped[JourneyType] = mapped_column(
        Enum(JourneyType, name="journey_type"), nullable=False, index=True
    )
    status: Mapped[JourneyStatus] = mapped_column(
        Enum(JourneyStatus, name="journey_status"),
        default=JourneyStatus.planned,
        nullable=False,
        index=True,
    )
    start_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    detected_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    signals: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
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

    scan: Mapped["Scan"] = relationship("Scan", back_populates="journeys")
