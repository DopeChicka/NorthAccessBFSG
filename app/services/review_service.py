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


class ReviewSubjectNotFoundError(Exception):
    pass


class ReviewItemValidationError(ValueError):
    pass


def create_review_item(
    db: Session,
    subject_type: str,
    subject_id: str,
    reason_code: str,
    priority: str = "medium",
    evidence: dict[str, Any] | None = None,
    notes: str | None = None,
) -> ReviewItem:
    return _create_review_item(
        db,
        subject_type=_coerce_subject_type(subject_type),
        subject_id=subject_id,
        reason_code=reason_code,
        priority=_coerce_priority(priority),
        evidence=evidence,
        notes=notes,
        commit=True,
    )


def _create_review_item(
    db: Session,
    *,
    subject_type: ReviewSubjectType,
    subject_id: str,
    reason_code: str,
    priority: ReviewPriority,
    evidence: dict[str, Any] | None = None,
    notes: str | None = None,
    commit: bool,
) -> ReviewItem:
    subject_type_value = _coerce_subject_type(subject_type)
    priority_value = _coerce_priority(priority)

    item = ReviewItem(
        subject_type=subject_type_value,
        subject_id=subject_id,
        status=ReviewItemStatus.pending,
        reason_code=reason_code,
        priority=priority_value,
        notes=notes,
        evidence={**(evidence or {}), "no_legal_conclusion": True},
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
    status: ReviewItemStatus | str,
    reviewer: str | None = None,
    notes: str | None = None,
) -> ReviewItem:
    item = get_review_item(db, review_item_id)
    status_value = _coerce_status(status)
    item.status = status_value
    item.reviewed_at = _reviewed_at_for_status(status_value)
    if notes is not None:
        item.notes = notes
    if reviewer is not None:
        item.reviewer = reviewer
    db.commit()
    db.refresh(item)
    return item


def create_review_for_compliance_mapping_if_required(
    db: Session, compliance_mapping_id: str
) -> ReviewItem | None:
    mapping = db.get(ComplianceMapping, compliance_mapping_id)
    if mapping is None:
        raise ReviewSubjectNotFoundError(
            f"Compliance mapping not found: {compliance_mapping_id}"
        )
    return auto_create_review_item_for_compliance_mapping(db, mapping, commit=True)


def create_review_for_finding_if_required(
    db: Session, finding_id: str
) -> ReviewItem | None:
    finding = db.get(Finding, finding_id)
    if finding is None:
        raise ReviewSubjectNotFoundError(f"Finding not found: {finding_id}")
    return auto_create_review_item_for_finding(db, finding, commit=True)


def create_review_for_website_probe_if_required(
    db: Session, website_probe_id: str
) -> ReviewItem | None:
    probe = db.get(WebsiteProbe, website_probe_id)
    if probe is None:
        raise ReviewSubjectNotFoundError(f"Website probe not found: {website_probe_id}")
    return auto_create_review_item_for_website_probe(db, probe, commit=True)


def auto_create_review_item_for_compliance_mapping(
    db: Session, mapping: ComplianceMapping, *, commit: bool = False
) -> ReviewItem | None:
    if not mapping.review_required:
        return None

    existing = _find_pending_review_item(
        db,
        subject_type=ReviewSubjectType.compliance_mapping,
        subject_id=mapping.id,
        reason_code="compliance_mapping_review_required",
    )
    if existing is not None:
        return existing

    return _create_review_item(
        db,
        subject_type=ReviewSubjectType.compliance_mapping,
        subject_id=mapping.id,
        reason_code="compliance_mapping_review_required",
        priority=ReviewPriority.medium,
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
    existing = _find_pending_review_item(
        db,
        subject_type=ReviewSubjectType.finding,
        subject_id=finding.id,
        reason_code="high_severity_finding_review",
    )
    if existing is not None:
        return existing

    return _create_review_item(
        db,
        subject_type=ReviewSubjectType.finding,
        subject_id=finding.id,
        reason_code="high_severity_finding_review",
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

    existing = _find_pending_review_item(
        db,
        subject_type=ReviewSubjectType.website_probe,
        subject_id=probe.id,
        reason_code="website_probe_needs_review",
    )
    if existing is not None:
        return existing

    return _create_review_item(
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


def _find_pending_review_item(
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
            ReviewItem.status == ReviewItemStatus.pending,
        )
        .one_or_none()
    )


def _coerce_subject_type(value: ReviewSubjectType | str) -> ReviewSubjectType:
    if isinstance(value, ReviewSubjectType):
        return value
    try:
        return ReviewSubjectType(value)
    except ValueError as exc:
        raise ReviewItemValidationError(f"Invalid subject_type: {value}") from exc


def _coerce_status(value: ReviewItemStatus | str) -> ReviewItemStatus:
    if isinstance(value, ReviewItemStatus):
        return value
    try:
        return ReviewItemStatus(value)
    except ValueError as exc:
        raise ReviewItemValidationError(f"Invalid status: {value}") from exc


def _coerce_priority(value: ReviewPriority | str) -> ReviewPriority:
    if isinstance(value, ReviewPriority):
        return value
    try:
        return ReviewPriority(value)
    except ValueError as exc:
        raise ReviewItemValidationError(f"Invalid priority: {value}") from exc


def _reviewed_at_for_status(status: ReviewItemStatus) -> datetime | None:
    if status == ReviewItemStatus.pending:
        return None
    return datetime.now(UTC)
