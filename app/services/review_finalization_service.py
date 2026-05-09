from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import (
    ComplianceMapping,
    Finding,
    ReviewItem,
    ReviewItemStatus,
    ReviewSubjectType,
    Scan,
    WebsiteProbe,
)


class ScanNotFoundError(Exception):
    pass


def summarize_scan_review_status(db: Session, scan_id: str) -> dict[str, object]:
    scan = db.get(Scan, scan_id)
    if scan is None:
        raise ScanNotFoundError(f"Scan not found: {scan_id}")

    items = _list_review_items_for_scan(db, scan)
    counts = {
        "pending_count": 0,
        "approved_count": 0,
        "rejected_count": 0,
        "needs_more_info_count": 0,
    }
    for item in items:
        if item.status == ReviewItemStatus.pending:
            counts["pending_count"] += 1
        elif item.status == ReviewItemStatus.approved:
            counts["approved_count"] += 1
        elif item.status == ReviewItemStatus.rejected:
            counts["rejected_count"] += 1
        elif item.status == ReviewItemStatus.needs_more_info:
            counts["needs_more_info_count"] += 1

    total_review_items = len(items)
    has_blocking_reviews = (
        counts["pending_count"] > 0 or counts["needs_more_info_count"] > 0
    )
    return {
        **counts,
        "total_review_items": total_review_items,
        "has_blocking_reviews": has_blocking_reviews,
        "no_legal_conclusion": True,
    }


def _list_review_items_for_scan(db: Session, scan: Scan) -> list[ReviewItem]:
    finding_ids = [
        finding.id
        for finding in (
            db.query(Finding)
            .filter(Finding.scan_id == scan.id)
            .order_by(Finding.created_at.asc(), Finding.id.asc())
            .all()
        )
    ]
    mapping_ids: list[str] = []
    if finding_ids:
        mapping_ids = [
            mapping.id
            for mapping in (
                db.query(ComplianceMapping)
                .filter(ComplianceMapping.finding_id.in_(finding_ids))
                .order_by(ComplianceMapping.created_at.asc(), ComplianceMapping.id.asc())
                .all()
            )
        ]

    candidate_id = (scan.evidence_metadata or {}).get("lead_candidate_id")
    website_probe_ids: list[str] = []
    if candidate_id:
        website_probe_ids = [
            probe.id
            for probe in (
                db.query(WebsiteProbe)
                .filter(WebsiteProbe.lead_candidate_id == candidate_id)
                .order_by(WebsiteProbe.created_at.asc(), WebsiteProbe.id.asc())
                .all()
            )
        ]

    subject_filters: list[tuple[ReviewSubjectType, list[str]]] = []
    if finding_ids:
        subject_filters.append((ReviewSubjectType.finding, finding_ids))
    if mapping_ids:
        subject_filters.append((ReviewSubjectType.compliance_mapping, mapping_ids))
    if candidate_id:
        subject_filters.append((ReviewSubjectType.candidate, [candidate_id]))
    if website_probe_ids:
        subject_filters.append((ReviewSubjectType.website_probe, website_probe_ids))

    if not subject_filters:
        return []

    review_items: list[ReviewItem] = []
    for subject_type, subject_ids in subject_filters:
        review_items.extend(
            db.query(ReviewItem)
            .filter(
                ReviewItem.subject_type == subject_type,
                ReviewItem.subject_id.in_(subject_ids),
            )
            .order_by(ReviewItem.created_at.asc(), ReviewItem.id.asc())
            .all()
        )
    return sorted(review_items, key=lambda item: (item.created_at, item.id))
