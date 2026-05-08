from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ComplianceMapping(Base):
    __tablename__ = "compliance_mappings"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    finding_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("findings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_rule_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    wcag_refs: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    en_301_549_refs: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    bfsg_signal_refs: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    review_required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    finding: Mapped["Finding"] = relationship("Finding", back_populates="compliance_mappings")
