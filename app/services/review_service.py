from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models import (
    ComplianceMapping,
    Finding,
    ReviewItem,
    ReviewItemStatus,
    ReviewPriority,
    ReviewSubjectType,
    WebsiteProbe,
    WebsiteProbeStatus,
)


class ReviewItemNotFoundError(Exception):
    pass


def create_review_item(
    db: Session,
    *,
    subject_type: ReviewSubjectType | str,
    subject_id: str,
    reason_code: str,
    priority: ReviewPriority | str = ReviewPriority.medium,
    notes: str | None = None,
    reviewer: str | None = None,
    evidence: dict[str, Any] | None = None,
    status: ReviewItemStatus | str = ReviewItemStatus.pending,
    commit: bool = True,
) -> ReviewItem:
    subject_type_value = _coerce_subject_type(subject_type)
    priority_value = _coerce_priority(priority)
    status_value = _coerce_status(status)
    existing = _find_existing_review_item(
        db,
        subject_type=subject_type_value,
        subject_id=subject_id,
        reason_code=reason_code,
    )
    if existing is not None:
        return existing

    item = ReviewItem(
        subject_type=subject_type_value,
        subject_id=subject_id,
        status=status_value,
        reason_code=reason_code,
        priority=priority_value,
        notes=notes,
        reviewer=reviewer,
        evidence={**(evidence or {}), "no_legal_conclusion": True},
        reviewed_at=_reviewed_at_for_status(status_value),
    )
    db.add(item)
    if commit:
        db.commit()
        db.refresh(item)
    else:
        db.flush()
    return item


def get_review_item(db: Session, review_item_id: str) -> ReviewItem:
    item = db.get(ReviewItem, review_item_id)
    if item is None:
        raise ReviewItemNotFoundError(f"Review item not found: {review_item_id}")
    return item


def list_review_items(
    db: Session,
    *,
    status: ReviewItemStatus | str | None = None,
    subject_type: ReviewSubjectType | str | None = None,
) -> list[ReviewItem]:
    query = db.query(ReviewItem)
    if status is not None:
        query = query.filter(ReviewItem.status == _coerce_status(status))
    if subject_type is not None:
        query = query.filter(ReviewItem.subject_type == _coerce_subject_type(subject_type))
    return query.order_by(
        ReviewItem.created_at.desc(),
        ReviewItem.id.desc(),
    ).all()


def update_review_item_status(
    db: Session,
    review_item_id: str,
    *,
    status: ReviewItemStatus | str,
    notes: str | None = None,
    reviewer: str | None = None,
    evidence: dict[str, Any] | None = None,
) -> ReviewItem:
    item = get_review_item(db, review_item_id)
    status_value = _coerce_status(status)
    item.status = status_value
    item.reviewed_at = _reviewed_at_for_status(status_value)
    if notes is not None:
        item.notes = notes
    if reviewer is not None:
        item.reviewer = reviewer
    if evidence is not None:
        item.evidence = {
            **(item.evidence or {}),
            **evidence,
            "no_legal_conclusion": True,
        }
    db.commit()
    db.refresh(item)
    return item


def auto_create_review_item_for_compliance_mapping(
    db: Session, mapping: ComplianceMapping, *, commit: bool = False
) -> ReviewItem | None:
    if not mapping.review_required:
        return None

    priority = (
        ReviewPriority.high
        if mapping.confidence_score <= 0.3
        else ReviewPriority.medium
    )
    return create_review_item(
        db,
        subject_type=ReviewSubjectType.compliance_mapping,
        subject_id=mapping.id,
        reason_code="compliance_mapping_review_required",
        priority=priority,
        evidence={
            "source": "compliance_mapping",
            "finding_id": mapping.finding_id,
            "source_rule_id": mapping.source_rule_id,
            "review_required": mapping.review_required,
            "confidence_score": mapping.confidence_score,
        },
        commit=commit,
    )


def auto_create_review_item_for_finding(
    db: Session, finding: Finding, *, commit: bool = False
) -> ReviewItem | None:
    if finding.review_status != "pending":
        return None

    severity = (finding.severity or "").lower()
    if severity not in {"critical", "high"}:
        return None

    priority = ReviewPriority.critical if severity == "critical" else ReviewPriority.high
    return create_review_item(
        db,
        subject_type=ReviewSubjectType.finding,
        subject_id=finding.id,
        reason_code="finding_priority_review",
        priority=priority,
        evidence={
            "source": "finding",
            "scan_id": finding.scan_id,
            "rule_id": finding.rule_id,
            "severity": severity,
            "review_status": finding.review_status,
        },
        commit=commit,
    )


def auto_create_review_item_for_website_probe(
    db: Session, probe: WebsiteProbe, *, commit: bool = False
) -> ReviewItem | None:
    if probe.status != WebsiteProbeStatus.needs_review:
        return None

    return create_review_item(
        db,
        subject_type=ReviewSubjectType.website_probe,
        subject_id=probe.id,
        reason_code="website_probe_needs_review",
        priority=ReviewPriority.medium,
        evidence={
            "source": "website_probe",
            "lead_candidate_id": probe.lead_candidate_id,
            "status": probe.status.value,
            "normalized_domain": probe.normalized_domain,
        },
        commit=commit,
    )


def _find_existing_review_item(
    db: Session,
    *,
    subject_type: ReviewSubjectType,
    subject_id: str,
    reason_code: str,
) -> ReviewItem | None:
    return (
        db.query(ReviewItem)
        .filter(
            ReviewItem.subject_type == subject_type,
            ReviewItem.subject_id == subject_id,
            ReviewItem.reason_code == reason_code,
        )
        .one_or_none()
    )


def _coerce_subject_type(value: ReviewSubjectType | str) -> ReviewSubjectType:
    return value if isinstance(value, ReviewSubjectType) else ReviewSubjectType(value)


def _coerce_status(value: ReviewItemStatus | str) -> ReviewItemStatus:
    return value if isinstance(value, ReviewItemStatus) else ReviewItemStatus(value)


def _coerce_priority(value: ReviewPriority | str) -> ReviewPriority:
    return value if isinstance(value, ReviewPriority) else ReviewPriority(value)


def _reviewed_at_for_status(status: ReviewItemStatus) -> datetime | None:
    if status == ReviewItemStatus.pending:
        return None
    return datetime.now(UTC)
