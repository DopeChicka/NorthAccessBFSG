from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models import Finding, Journey, JourneyStatus, Scan, ScanEvidence
from app.services.axe_homepage_service import (
    AxeHomepageResult,
    AxeHomepageRunner,
    AxeViolation,
    _confidence_for_violation,
    _run_playwright_axe_homepage,
    _sample_node_targets,
)
from app.services.review_service import auto_create_review_item_for_finding

_SEVERITY_BY_AXE_IMPACT = {
    "critical": "critical",
    "serious": "high",
    "moderate": "medium",
    "minor": "low",
}


class JourneyNotFoundError(Exception):
    pass


class AxeJourneyAuditError(Exception):
    pass


class ScanNotFoundError(Exception):
    pass


def run_axe_for_journey(
    db: Session,
    journey_id: str,
    *,
    runner: AxeHomepageRunner | None = None,
) -> list[Finding]:
    journey = db.get(Journey, journey_id)
    if journey is None:
        raise JourneyNotFoundError(f"Journey not found: {journey_id}")

    target_url = journey.detected_url or journey.start_url
    if target_url is None:
        _mark_journey_failed(db, journey, "Journey has no URL for axe audit")
        raise AxeJourneyAuditError("Journey has no URL for axe audit")

    journey.status = JourneyStatus.running
    journey.error_message = None
    db.commit()

    try:
        result = (runner or _run_playwright_axe_homepage)(target_url)
    except Exception as exc:
        _mark_journey_failed(db, journey, "Journey axe audit failed")
        raise AxeJourneyAuditError("Journey axe audit failed") from exc

    evidence = _create_axe_journey_evidence(db, journey, result)
    findings: list[Finding] = []
    for violation in result.violations:
        finding = _finding_from_violation(journey, evidence, result, violation)
        db.add(finding)
        db.flush()
        auto_create_review_item_for_finding(db, finding)
        findings.append(finding)

    journey.status = JourneyStatus.done
    journey.executed_at = datetime.now(UTC)
    journey.detected_url = result.final_url
    journey.evidence = {
        **(journey.evidence or {}),
        "axe_journey": {
            "evidence_id": evidence.id,
            "findings_count": len(findings),
            "no_legal_conclusion": True,
        },
        "no_legal_conclusion": True,
    }
    db.commit()
    for finding in findings:
        db.refresh(finding)
    return findings


def run_axe_for_scan_journeys(
    db: Session,
    scan_id: str,
    *,
    runner: AxeHomepageRunner | None = None,
) -> list[Finding]:
    scan = db.get(Scan, scan_id)
    if scan is None:
        raise ScanNotFoundError(f"Scan not found: {scan_id}")

    journeys = (
        db.query(Journey)
        .filter(
            Journey.scan_id == scan_id,
            Journey.status != JourneyStatus.skipped,
        )
        .order_by(Journey.journey_type.asc(), Journey.id.asc())
        .all()
    )
    findings: list[Finding] = []
    for journey in journeys:
        findings.extend(run_axe_for_journey(db, journey.id, runner=runner))
    return findings


def _create_axe_journey_evidence(
    db: Session, journey: Journey, result: AxeHomepageResult
) -> ScanEvidence:
    metadata = {
        "target_url": result.target_url,
        "final_url": result.final_url,
        "page_title": result.page_title,
        "http_status": result.http_status,
        "timestamp": result.captured_at,
        "journey_type": journey.journey_type.value,
        "findings_count": len(result.violations),
        "no_crawling": True,
        "no_forms": True,
        "no_legal_conclusion": True,
    }
    evidence = ScanEvidence(
        scan_id=journey.scan_id,
        evidence_type="axe_journey",
        related_entity_type="journey",
        related_entity_id=journey.id,
        path_or_key=f"scan-evidence/{journey.scan_id}/journeys/{journey.id}/axe.json",
        evidence_metadata=metadata,
        hash=None,
    )
    db.add(evidence)
    db.flush()
    return evidence


def _finding_from_violation(
    journey: Journey,
    evidence: ScanEvidence,
    result: AxeHomepageResult,
    violation: AxeViolation,
) -> Finding:
    impact = violation.impact or "unknown"
    node_count = len(violation.nodes)
    finding_evidence = {
        "scan_evidence_id": evidence.id,
        "journey_id": journey.id,
        "journey_type": journey.journey_type.value,
        "target_url": result.target_url,
        "final_url": result.final_url,
        "impact": impact,
        "node_count": node_count,
        "sample_targets": _sample_node_targets(violation.nodes),
        "no_legal_conclusion": True,
    }
    return Finding(
        scan_id=journey.scan_id,
        journey_id=journey.id,
        rule_id=violation.rule_id,
        severity=_SEVERITY_BY_AXE_IMPACT.get(impact, "info"),
        description=violation.description,
        help_url=violation.help_url,
        wcag_refs=violation.wcag_refs,
        evidence=finding_evidence,
        confidence_score=_confidence_for_violation(
            impact=impact,
            node_count=node_count,
        ),
        review_status="pending",
        evidence_metadata=finding_evidence,
    )


def _mark_journey_failed(db: Session, journey: Journey, message: str) -> None:
    journey.status = JourneyStatus.failed
    journey.error_message = message
    db.commit()
