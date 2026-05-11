from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Enum, Float, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

DEFAULT_FINDING_LEGAL_DISCLAIMER = (
    "Technischer Hinweis, keine Rechtsberatung. Manuelle Prüfung empfohlen."
)


class FindingCategory(str, enum.Enum):
    accessibility = "accessibility"
    technical = "technical"
    privacy = "privacy"
    seo = "seo"


class FindingResponsibleRole(str, enum.Enum):
    developer = "developer"
    content = "content"
    design = "design"
    ux = "ux"
    auditor = "auditor"


class Finding(Base):
    __tablename__ = "findings"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    scan_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("scans.id", ondelete="CASCADE"), nullable=False, index=True
    )
    journey_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("journeys.id", ondelete="SET NULL"), nullable=True, index=True
    )
    category: Mapped[FindingCategory] = mapped_column(
        Enum(FindingCategory, name="finding_category"),
        default=FindingCategory.accessibility,
        nullable=False,
        index=True,
    )
    rule_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    help_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    wcag_refs: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    evidence: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    technical_evidence: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, nullable=False
    )
    source_tool: Mapped[str] = mapped_column(String(100), default="unknown", nullable=False)
    recommendation: Mapped[str | None] = mapped_column(Text, nullable=True)
    responsible_role: Mapped[FindingResponsibleRole] = mapped_column(
        Enum(FindingResponsibleRole, name="finding_responsible_role"),
        default=FindingResponsibleRole.developer,
        nullable=False,
        index=True,
    )
    manual_review_required: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False, index=True
    )
    legal_disclaimer: Mapped[str] = mapped_column(
        Text,
        default=DEFAULT_FINDING_LEGAL_DISCLAIMER,
        nullable=False,
    )
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    review_status: Mapped[str] = mapped_column(
        String(50), default="pending", nullable=False, index=True
    )
    evidence_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    scan: Mapped["Scan"] = relationship("Scan", back_populates="findings")
    compliance_mappings: Mapped[list["ComplianceMapping"]] = relationship(
        "ComplianceMapping", back_populates="finding", cascade="all, delete-orphan"
    )
