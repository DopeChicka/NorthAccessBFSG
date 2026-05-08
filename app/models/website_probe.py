from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class WebsiteProbeStatus(str, enum.Enum):
    pending = "pending"
    skipped = "skipped"
    reachable = "reachable"
    unreachable = "unreachable"
    needs_review = "needs_review"


class WebsiteProbe(Base):
    __tablename__ = "website_probes"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    lead_candidate_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("lead_candidates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    promotion_decision_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("promotion_decisions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    normalized_domain: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[WebsiteProbeStatus] = mapped_column(
        Enum(WebsiteProbeStatus, name="website_probe_status"),
        default=WebsiteProbeStatus.pending,
        nullable=False,
        index=True,
    )
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    has_homepage_signal: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    has_impressum_signal: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    has_login_signal: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    has_shop_signal: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    has_booking_signal: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    has_checkout_signal: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    has_b2c_transaction_signal: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    lead_candidate: Mapped["LeadCandidate"] = relationship(
        "LeadCandidate", back_populates="website_probes"
    )
    promotion_decision: Mapped["PromotionDecision | None"] = relationship(
        "PromotionDecision"
    )
