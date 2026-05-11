from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models import (
    ComplianceMapping,
    Finding,
    Journey,
    Report,
    ReportStatus,
    ReportType,
    ReviewItem,
    ReviewItemStatus,
    ReviewSubjectType,
    Scan,
    WebsiteProbe,
)
from app.services.evidence_manifest_service import build_evidence_manifest
from app.services.evidence_quality_service import assess_scan_evidence_quality
from app.services.review_finalization_service import summarize_scan_review_status


class ScanNotFoundError(Exception):
    pass


class ReportNotFoundError(Exception):
    pass


def generate_scan_json_report(db: Session, scan_id: str) -> Report:
    scan = db.get(Scan, scan_id)
    if scan is None:
        raise ScanNotFoundError(f"Scan not found: {scan_id}")

    report = Report(
        scan_id=scan_id,
        status=ReportStatus.pending,
        report_type=ReportType.json,
        summary={},
        output={},
        evidence_manifest={},
    )
    db.add(report)
    db.flush()

    try:
        generated_at = datetime.now(UTC)
        evidence_manifest = build_evidence_manifest(db, scan_id)
        evidence_quality = assess_scan_evidence_quality(db, scan_id)
        journeys = _list_journeys(db, scan_id)
        findings = _list_findings(db, scan_id)
        compliance_mappings = _list_compliance_mappings(db, findings)
        review_items = _list_review_items(db, scan, findings, compliance_mappings)
        review_summary = summarize_scan_review_status(db, scan_id)
        finding_review_outcomes = _build_finding_review_outcomes(findings, review_items)
        summary = _build_summary(
            findings=findings,
            compliance_mappings=compliance_mappings,
            review_items=review_items,
            evidence_manifest=evidence_manifest,
            finding_review_outcomes=finding_review_outcomes,
        )
        output = {
            "report_id": report.id,
            "report_type": ReportType.json.value,
            "generated_at": generated_at.isoformat(),
            "scan": _serialize_scan(scan),
            "journeys": [_serialize_journey(journey) for journey in journeys],
            "findings": [
                _serialize_finding(
                    finding,
                    review_outcome=finding_review_outcomes[finding.id]["review_outcome"],
                    excluded_from_final_summary=finding_review_outcomes[finding.id][
                        "excluded_from_final_summary"
                    ],
                )
                for finding in findings
            ],
            "compliance_mappings": [
                _serialize_compliance_mapping(mapping)
                for mapping in compliance_mappings
            ],
            "review_items": [_serialize_review_item(item) for item in review_items],
            "evidence_manifest": evidence_manifest,
            "evidence_quality": evidence_quality,
            "review_summary": review_summary,
            "reviewed_finding_count": summary["reviewed_finding_count"],
            "rejected_finding_count": summary["rejected_finding_count"],
            "pending_review_count": summary["pending_review_count"],
            "summary": summary,
            "no_legal_conclusion": True,
        }
        report.status = ReportStatus.generated
        report.summary = summary
        report.output = output
        report.evidence_manifest = evidence_manifest
        report.generated_at = generated_at
        report.error_message = None
    except Exception as exc:
        report.status = ReportStatus.failed
        report.error_message = "JSON report generation failed"
        db.commit()
        raise RuntimeError("JSON report generation failed") from exc

    db.commit()
    db.refresh(report)
    return report


def get_report(db: Session, report_id: str) -> Report:
    report = db.get(Report, report_id)
    if report is None:
        raise ReportNotFoundError(f"Report not found: {report_id}")
    return report


def list_reports_for_scan(db: Session, scan_id: str) -> list[Report]:
    scan = db.get(Scan, scan_id)
    if scan is None:
        raise ScanNotFoundError(f"Scan not found: {scan_id}")

    return (
        db.query(Report)
        .filter(Report.scan_id == scan_id)
        .order_by(Report.created_at.desc(), Report.id.desc())
        .all()
    )


def _list_findings(db: Session, scan_id: str) -> list[Finding]:
    return (
        db.query(Finding)
        .filter(Finding.scan_id == scan_id)
        .order_by(Finding.created_at.asc(), Finding.id.asc())
        .all()
    )


def _list_journeys(db: Session, scan_id: str) -> list[Journey]:
    return (
        db.query(Journey)
        .filter(Journey.scan_id == scan_id)
        .order_by(Journey.journey_type.asc(), Journey.id.asc())
        .all()
    )


def _list_compliance_mappings(
    db: Session, findings: list[Finding]
) -> list[ComplianceMapping]:
    finding_ids = [finding.id for finding in findings]
    if not finding_ids:
        return []

    return (
        db.query(ComplianceMapping)
        .filter(ComplianceMapping.finding_id.in_(finding_ids))
        .order_by(ComplianceMapping.created_at.asc(), ComplianceMapping.id.asc())
        .all()
    )


def _list_review_items(
    db: Session,
    scan: Scan,
    findings: list[Finding],
    compliance_mappings: list[ComplianceMapping],
) -> list[ReviewItem]:
    subject_filters: list[tuple[ReviewSubjectType, list[str]]] = []
    finding_ids = [finding.id for finding in findings]
    mapping_ids = [mapping.id for mapping in compliance_mappings]
    candidate_id = (scan.evidence_metadata or {}).get("lead_candidate_id")
    website_probe_ids = _website_probe_ids_for_candidate(db, candidate_id)

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

    items: list[ReviewItem] = []
    for subject_type, subject_ids in subject_filters:
        items.extend(
            db.query(ReviewItem)
            .filter(
                ReviewItem.subject_type == subject_type,
                ReviewItem.subject_id.in_(subject_ids),
            )
            .order_by(ReviewItem.created_at.asc(), ReviewItem.id.asc())
            .all()
        )
    return sorted(items, key=lambda item: (item.created_at, item.id))


def _website_probe_ids_for_candidate(db: Session, candidate_id: str | None) -> list[str]:
    if not candidate_id:
        return []

    return [
        probe.id
        for probe in (
            db.query(WebsiteProbe)
            .filter(WebsiteProbe.lead_candidate_id == candidate_id)
            .order_by(WebsiteProbe.created_at.asc(), WebsiteProbe.id.asc())
            .all()
        )
    ]


def _build_summary(
    *,
    findings: list[Finding],
    compliance_mappings: list[ComplianceMapping],
    review_items: list[ReviewItem],
    evidence_manifest: dict[str, Any],
    finding_review_outcomes: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for finding in findings:
        severity = (finding.severity or "").lower()
        if severity in severity_counts:
            severity_counts[severity] += 1

    reviewed_finding_count = sum(
        1
        for outcome in finding_review_outcomes.values()
        if outcome["review_outcome"] in {"approved", "rejected"}
    )
    rejected_finding_count = sum(
        1
        for outcome in finding_review_outcomes.values()
        if outcome["review_outcome"] == "rejected"
    )
    pending_review_count = sum(
        1
        for outcome in finding_review_outcomes.values()
        if outcome["review_outcome"] == "pending"
    )

    return {
        "finding_count": len(findings),
        "compliance_mapping_count": len(compliance_mappings),
        "review_item_count": len(review_items),
        "evidence_count": evidence_manifest["evidence_count"],
        "reviewed_finding_count": reviewed_finding_count,
        "rejected_finding_count": rejected_finding_count,
        "pending_review_count": pending_review_count,
        "critical_count": severity_counts["critical"],
        "high_count": severity_counts["high"],
        "medium_count": severity_counts["medium"],
        "low_count": severity_counts["low"],
        "no_legal_conclusion": True,
    }


def _serialize_scan(scan: Scan) -> dict[str, Any]:
    return {
        "id": scan.id,
        "lead_id": scan.lead_id,
        "status": scan.status.value,
        "created_at": scan.created_at.isoformat() if scan.created_at else None,
        "started_at": scan.started_at.isoformat() if scan.started_at else None,
        "completed_at": scan.completed_at.isoformat() if scan.completed_at else None,
        "failed_at": scan.failed_at.isoformat() if scan.failed_at else None,
        "evidence_metadata": scan.evidence_metadata,
        "no_legal_conclusion": True,
    }


def _serialize_finding(
    finding: Finding,
    *,
    review_outcome: str = "pending",
    excluded_from_final_summary: bool = False,
) -> dict[str, Any]:
    return {
        "id": finding.id,
        "scan_id": finding.scan_id,
        "journey_id": finding.journey_id,
        "category": finding.category.value if finding.category else None,
        "rule_id": finding.rule_id,
        "severity": finding.severity,
        "title": finding.title,
        "description": finding.description,
        "help_url": finding.help_url,
        "wcag_refs": finding.wcag_refs,
        "evidence": finding.evidence,
        "technical_evidence": finding.technical_evidence,
        "source_tool": finding.source_tool,
        "recommendation": finding.recommendation,
        "responsible_role": finding.responsible_role.value
        if finding.responsible_role
        else None,
        "manual_review_required": finding.manual_review_required,
        "legal_disclaimer": finding.legal_disclaimer,
        "confidence_score": finding.confidence_score,
        "review_status": finding.review_status,
        "review_outcome": review_outcome,
        "excluded_from_final_summary": excluded_from_final_summary,
        "evidence_metadata": finding.evidence_metadata,
        "created_at": finding.created_at.isoformat() if finding.created_at else None,
        "signal_only": True,
        "no_legal_conclusion": True,
    }


def _serialize_journey(journey: Journey) -> dict[str, Any]:
    return {
        "id": journey.id,
        "scan_id": journey.scan_id,
        "journey_type": journey.journey_type.value,
        "status": journey.status.value,
        "start_url": journey.start_url,
        "detected_url": journey.detected_url,
        "signals": journey.signals,
        "evidence": journey.evidence,
        "created_at": journey.created_at.isoformat() if journey.created_at else None,
        "updated_at": journey.updated_at.isoformat() if journey.updated_at else None,
        "executed_at": journey.executed_at.isoformat() if journey.executed_at else None,
        "error_message": journey.error_message,
        "planned_signal_only": True,
        "no_legal_conclusion": True,
    }


def _serialize_compliance_mapping(mapping: ComplianceMapping) -> dict[str, Any]:
    return {
        "id": mapping.id,
        "finding_id": mapping.finding_id,
        "source_rule_id": mapping.source_rule_id,
        "wcag_refs": mapping.wcag_refs,
        "en_301_549_refs": mapping.en_301_549_refs,
        "bfsg_signal_refs": mapping.bfsg_signal_refs,
        "review_required": mapping.review_required,
        "confidence_score": mapping.confidence_score,
        "evidence": mapping.evidence,
        "created_at": mapping.created_at.isoformat() if mapping.created_at else None,
        "reference_signal_only": True,
        "no_legal_conclusion": True,
    }


def _serialize_review_item(item: ReviewItem) -> dict[str, Any]:
    return {
        "id": item.id,
        "subject_type": item.subject_type.value,
        "subject_id": item.subject_id,
        "status": item.status.value,
        "reason_code": item.reason_code,
        "priority": item.priority.value,
        "notes": item.notes,
        "reviewer": item.reviewer,
        "evidence": item.evidence,
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
        "reviewed_at": item.reviewed_at.isoformat() if item.reviewed_at else None,
        "human_workflow_only": True,
        "no_legal_conclusion": True,
    }


def _build_finding_review_outcomes(
    findings: list[Finding],
    review_items: list[ReviewItem],
) -> dict[str, dict[str, Any]]:
    status_by_finding: dict[str, list[ReviewItemStatus]] = {
        finding.id: [] for finding in findings
    }
    for item in review_items:
        if item.subject_type != ReviewSubjectType.finding:
            continue
        if item.subject_id not in status_by_finding:
            continue
        status_by_finding[item.subject_id].append(item.status)

    outcomes: dict[str, dict[str, Any]] = {}
    for finding in findings:
        statuses = status_by_finding.get(finding.id, [])
        if ReviewItemStatus.rejected in statuses:
            review_outcome = "rejected"
        elif ReviewItemStatus.approved in statuses:
            review_outcome = "approved"
        else:
            review_outcome = "pending"

        outcomes[finding.id] = {
            "review_outcome": review_outcome,
            "excluded_from_final_summary": review_outcome == "rejected",
            "no_legal_conclusion": True,
        }
    return outcomes
