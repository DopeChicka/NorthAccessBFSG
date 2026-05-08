from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class CompanyEnrichment(Base):
    __tablename__ = "company_enrichments"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    lead_candidate_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("lead_candidates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    source_reference: Mapped[str | None] = mapped_column(String(500), nullable=True)
    company_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    legal_form: Mapped[str | None] = mapped_column(String(100), nullable=True)
    registry_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    employee_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    annual_revenue_eur: Mapped[int | None] = mapped_column(Integer, nullable=True)
    balance_sheet_total_eur: Mapped[int | None] = mapped_column(Integer, nullable=True)
    raw_data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
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
        "LeadCandidate", back_populates="enrichments"
    )
