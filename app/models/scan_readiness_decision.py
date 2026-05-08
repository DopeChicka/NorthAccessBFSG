from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Enum, Float, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ScanReadinessStatus(str, enum.Enum):
    rejected = "rejected"
    needs_review = "needs_review"
    ready_for_scan = "ready_for_scan"


class ScanReadinessReasonCode(str, enum.Enum):
    missing_promotion_decision = "missing_promotion_decision"
    promotion_not_ready = "promotion_not_ready"
    missing_website_probe = "missing_website_probe"
    missing_domain = "missing_domain"
    website_probe_not_reachable = "website_probe_not_reachable"
    missing_b2c_transaction_signal = "missing_b2c_transaction_signal"
    ready_for_scan = "ready_for_scan"


class ScanReadinessDecision(Base):
    __tablename__ = "scan_readiness_decisions"

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
    website_probe_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("website_probes.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status: Mapped[ScanReadinessStatus] = mapped_column(
        Enum(ScanReadinessStatus, name="scan_readiness_status"),
        nullable=False,
        index=True,
    )
    reason_code: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    reasons: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
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
        "LeadCandidate", back_populates="scan_readiness_decisions"
    )
    promotion_decision: Mapped["PromotionDecision | None"] = relationship(
        "PromotionDecision"
    )
    website_probe: Mapped["WebsiteProbe | None"] = relationship("WebsiteProbe")
