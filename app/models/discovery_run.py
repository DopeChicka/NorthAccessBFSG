from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Enum, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class DiscoveryRunStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    done = "done"
    failed = "failed"


class DiscoveryRun(Base):
    __tablename__ = "discovery_runs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    city: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    normalized_city: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    status: Mapped[DiscoveryRunStatus] = mapped_column(
        Enum(DiscoveryRunStatus, name="discovery_run_status"),
        default=DiscoveryRunStatus.pending,
        nullable=False,
    )
    keyword_groups: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, default=list, nullable=False
    )
    postal_codes: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    query_plan: Mapped[list[dict[str, str]]] = mapped_column(
        JSON, default=list, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    candidates: Mapped[list["LeadCandidate"]] = relationship(
        "LeadCandidate",
        back_populates="discovery_run",
        cascade="all, delete-orphan",
    )
