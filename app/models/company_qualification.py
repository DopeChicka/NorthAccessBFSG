from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class CompanyQualificationStatus(str, enum.Enum):
    pending = "pending"
    needs_company_data = "needs_company_data"
    likely_not_applicable = "likely_not_applicable"
    possible_bfsg_candidate = "possible_bfsg_candidate"
    needs_human_review = "needs_human_review"
    rejected = "rejected"


class CompanyQualification(Base):
    __tablename__ = "company_qualifications"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    lead_candidate_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("lead_candidates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[CompanyQualificationStatus] = mapped_column(
        Enum(CompanyQualificationStatus, name="company_qualification_status"),
        default=CompanyQualificationStatus.pending,
        nullable=False,
        index=True,
    )
    company_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    legal_form: Mapped[str | None] = mapped_column(String(100), nullable=True)
    registry_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    northdata_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    employee_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    annual_revenue_eur: Mapped[int | None] = mapped_column(Integer, nullable=True)
    balance_sheet_total_eur: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_microenterprise: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    b2c_signal: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    bfsg_category_signal: Mapped[str | None] = mapped_column(String(255), nullable=True)
    website_signal: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
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
        "LeadCandidate", back_populates="qualifications"
    )
