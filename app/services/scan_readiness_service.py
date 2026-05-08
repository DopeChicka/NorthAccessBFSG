from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.lead import Lead
from app.models.lead_candidate import LeadCandidate
from app.models.promotion_decision import PromotionDecision, PromotionDecisionStatus
from app.models.scan import Scan, ScanStatus
from app.models.scan_readiness_decision import (
    ScanReadinessDecision,
    ScanReadinessReasonCode,
    ScanReadinessStatus,
)
from app.models.website_probe import WebsiteProbe, WebsiteProbeStatus
from app.services.company_qualification_service import LeadCandidateNotFoundError


class ScanReadinessNotReadyError(Exception):
    pass


def evaluate_candidate_for_scan_readiness(
    db: Session, candidate_id: str
) -> ScanReadinessDecision:
    candidate = db.get(LeadCandidate, candidate_id)
    if candidate is None:
        raise LeadCandidateNotFoundError(f"Lead candidate not found: {candidate_id}")

    promotion = _get_latest_promotion_decision(db, candidate_id)
    website_probe = _get_latest_website_probe(db, candidate_id)
    status, reason_code, confidence_score = _decide(promotion, website_probe)
    decision = ScanReadinessDecision(
        lead_candidate_id=candidate.id,
        promotion_decision_id=promotion.id if promotion else None,
        website_probe_id=website_probe.id if website_probe else None,
        status=status,
        reason_code=reason_code.value,
        reasons=_build_reasons(candidate, promotion, website_probe),
        confidence_score=confidence_score,
    )
    db.add(decision)
    db.commit()
    db.refresh(decision)
    return decision


def get_latest_scan_readiness_decision(
    db: Session, candidate_id: str
) -> ScanReadinessDecision | None:
    candidate = db.get(LeadCandidate, candidate_id)
    if candidate is None:
        raise LeadCandidateNotFoundError(f"Lead candidate not found: {candidate_id}")

    return (
        db.query(ScanReadinessDecision)
        .filter(ScanReadinessDecision.lead_candidate_id == candidate_id)
        .order_by(
            ScanReadinessDecision.created_at.desc(),
            ScanReadinessDecision.id.desc(),
        )
        .first()
    )


def create_scan_skeleton_for_candidate(db: Session, candidate_id: str) -> Scan:
    candidate = db.get(LeadCandidate, candidate_id)
    if candidate is None:
        raise LeadCandidateNotFoundError(f"Lead candidate not found: {candidate_id}")

    decision = get_latest_scan_readiness_decision(db, candidate_id)
    if decision is None:
        raise ScanReadinessNotReadyError(
            f"Scan readiness decision not found for candidate: {candidate_id}"
        )
    if decision.status != ScanReadinessStatus.ready_for_scan:
        raise ScanReadinessNotReadyError(
            f"Candidate is not ready for scan: {decision.status.value}"
        )

    website_probe = db.get(WebsiteProbe, decision.website_probe_id)
    if website_probe is None or not (candidate.domain or website_probe.normalized_domain):
        raise ScanReadinessNotReadyError(
            f"Candidate is not ready for scan: {ScanReadinessReasonCode.missing_domain.value}"
        )
    lead = _get_or_create_lead(db, candidate, website_probe)
    scan = Scan(
        lead_id=lead.id,
        status=ScanStatus.pending,
        evidence_metadata={
            "source": "scan_job_skeleton",
            "lead_candidate_id": candidate.id,
            "scan_readiness_decision_id": decision.id,
            "no_legal_conclusion": True,
        },
    )
    db.add(scan)
    db.commit()
    db.refresh(scan)
    return scan


def _decide(
    promotion: PromotionDecision | None,
    website_probe: WebsiteProbe | None,
) -> tuple[ScanReadinessStatus, ScanReadinessReasonCode, float | None]:
    if website_probe is None:
        return (
            ScanReadinessStatus.rejected,
            ScanReadinessReasonCode.missing_website_probe,
            0.2,
        )

    if promotion is None:
        return (
            ScanReadinessStatus.needs_review,
            ScanReadinessReasonCode.missing_promotion_decision,
            website_probe.confidence_score,
        )

    if promotion.status != PromotionDecisionStatus.ready_for_website_probe:
        status = (
            ScanReadinessStatus.rejected
            if promotion.status == PromotionDecisionStatus.rejected
            else ScanReadinessStatus.needs_review
        )
        return (status, ScanReadinessReasonCode.promotion_not_ready, 0.2)

    if not website_probe.url or not website_probe.normalized_domain:
        return (
            ScanReadinessStatus.needs_review,
            ScanReadinessReasonCode.missing_domain,
            website_probe.confidence_score,
        )

    if website_probe.status != WebsiteProbeStatus.reachable:
        return (
            ScanReadinessStatus.needs_review,
            ScanReadinessReasonCode.website_probe_not_reachable,
            website_probe.confidence_score,
        )

    if website_probe.has_b2c_transaction_signal is not True:
        return (
            ScanReadinessStatus.needs_review,
            ScanReadinessReasonCode.missing_b2c_transaction_signal,
            website_probe.confidence_score,
        )

    return (
        ScanReadinessStatus.ready_for_scan,
        ScanReadinessReasonCode.ready_for_scan,
        website_probe.confidence_score,
    )


def _build_reasons(
    candidate: LeadCandidate,
    promotion: PromotionDecision | None,
    website_probe: WebsiteProbe | None,
) -> dict[str, object]:
    return {
        "candidate_source": candidate.source,
        "category": candidate.category,
        "has_candidate_domain": bool(candidate.domain),
        "promotion_status": promotion.status.value if promotion else None,
        "website_probe_status": website_probe.status.value if website_probe else None,
        "website_probe_has_domain": bool(
            website_probe and website_probe.normalized_domain and website_probe.url
        ),
        "website_probe_reachable": (
            website_probe.status == WebsiteProbeStatus.reachable
            if website_probe
            else None
        ),
        "b2c_transaction_signal": (
            website_probe.has_b2c_transaction_signal if website_probe else None
        ),
        "no_legal_conclusion": True,
    }


def _get_latest_promotion_decision(
    db: Session, candidate_id: str
) -> PromotionDecision | None:
    return (
        db.query(PromotionDecision)
        .filter(PromotionDecision.lead_candidate_id == candidate_id)
        .order_by(PromotionDecision.created_at.desc(), PromotionDecision.id.desc())
        .first()
    )


def _get_latest_website_probe(db: Session, candidate_id: str) -> WebsiteProbe | None:
    return (
        db.query(WebsiteProbe)
        .filter(WebsiteProbe.lead_candidate_id == candidate_id)
        .order_by(WebsiteProbe.created_at.desc(), WebsiteProbe.id.desc())
        .first()
    )


def _get_or_create_lead(
    db: Session,
    candidate: LeadCandidate,
    website_probe: WebsiteProbe | None,
) -> Lead:
    domain = candidate.domain or (website_probe.normalized_domain if website_probe else "")
    lead = db.query(Lead).filter(Lead.domain == domain).first()
    if lead:
        return lead

    lead = Lead(
        domain=domain,
        company_name=candidate.company_name or "Unknown company",
    )
    db.add(lead)
    db.flush()
    return lead


__all__ = [
    "ScanReadinessNotReadyError",
    "create_scan_skeleton_for_candidate",
    "evaluate_candidate_for_scan_readiness",
    "get_latest_scan_readiness_decision",
]
