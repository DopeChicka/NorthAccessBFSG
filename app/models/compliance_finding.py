from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Float, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ComplianceFinding(Base):
    __tablename__ = "compliance_findings"
    __table_args__ = (
        UniqueConstraint(
            "finding_id",
            "mapping_version",
            name="uq_compliance_findings_finding_mapping_version",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    scan_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("scans.id", ondelete="CASCADE"), nullable=False, index=True
    )
    finding_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("findings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    rule_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    mapping_version: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    wcag_refs: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    en_refs: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    bfsg_refs: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    bfsg_category: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    normalized_severity: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    compliance_confidence_score: Mapped[float] = mapped_column(Float, nullable=False)
    mapping_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    scan: Mapped["Scan"] = relationship("Scan")
    finding: Mapped["Finding"] = relationship("Finding")
