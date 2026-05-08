from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Enum, Float, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class PromotionDecisionStatus(str, enum.Enum):
    rejected = "rejected"
    needs_review = "needs_review"
    ready_for_website_probe = "ready_for_website_probe"


class PromotionReasonCode(str, enum.Enum):
    missing_company_data = "missing_company_data"
    missing_website = "missing_website"
    likely_microenterprise = "likely_microenterprise"
    mock_or_test_data = "mock_or_test_data"
    insufficient_bfsg_signal = "insufficient_bfsg_signal"
    possible_bfsg_candidate = "possible_bfsg_candidate"
    needs_human_review = "needs_human_review"


class PromotionDecision(Base):
    __tablename__ = "promotion_decisions"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    lead_candidate_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("lead_candidates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    company_qualification_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("company_qualifications.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    company_enrichment_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("company_enrichments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status: Mapped[PromotionDecisionStatus] = mapped_column(
        Enum(PromotionDecisionStatus, name="promotion_decision_status"),
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
        "LeadCandidate", back_populates="promotion_decisions"
    )
    company_qualification: Mapped["CompanyQualification | None"] = relationship(
        "CompanyQualification"
    )
    company_enrichment: Mapped["CompanyEnrichment | None"] = relationship(
        "CompanyEnrichment"
    )
