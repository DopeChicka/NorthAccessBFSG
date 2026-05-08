from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.lead_candidate import LeadCandidate
from app.models.promotion_decision import PromotionDecision, PromotionDecisionStatus
from app.models.website_probe import WebsiteProbe, WebsiteProbeStatus
from app.services.company_qualification_service import LeadCandidateNotFoundError
from app.website_probe.providers.base import WebsiteProbeProvider, WebsiteProbeResult
from app.website_probe.providers.http_provider import HttpWebsiteProbeProvider
from app.website_probe.providers.mock_provider import MockWebsiteProbeProvider


def run_mock_website_probe(db: Session, candidate_id: str) -> WebsiteProbe:
    candidate = db.get(LeadCandidate, candidate_id)
    if candidate is None:
        raise LeadCandidateNotFoundError(f"Lead candidate not found: {candidate_id}")

    promotion = _get_latest_promotion_decision(db, candidate_id)
    if promotion and promotion.status == PromotionDecisionStatus.rejected:
        result = WebsiteProbeResult(
            url=None,
            normalized_domain=None,
            status=WebsiteProbeStatus.skipped.value,
            evidence={
                "reason": "rejected_by_promotion_gate",
                "promotion_status": promotion.status.value,
                "promotion_decision_id": promotion.id,
                "no_legal_conclusion": True,
            },
            confidence_score=0.2,
        )
    else:
        result = MockWebsiteProbeProvider().probe(candidate)
        evidence = dict(result.evidence or {})
        if promotion:
            evidence["promotion_status"] = promotion.status.value
            evidence["promotion_decision_id"] = promotion.id
        result = WebsiteProbeResult(
            url=result.url,
            normalized_domain=result.normalized_domain,
            status=result.status,
            http_status=result.http_status,
            has_homepage_signal=result.has_homepage_signal,
            has_impressum_signal=result.has_impressum_signal,
            has_login_signal=result.has_login_signal,
            has_shop_signal=result.has_shop_signal,
            has_booking_signal=result.has_booking_signal,
            has_checkout_signal=result.has_checkout_signal,
            has_b2c_transaction_signal=result.has_b2c_transaction_signal,
            evidence=evidence,
            confidence_score=result.confidence_score,
        )

    existing = _find_existing_probe(db, candidate_id, promotion, result)
    if existing:
        return existing

    probe = _probe_from_result(candidate_id, promotion, result)
    db.add(probe)
    db.commit()
    db.refresh(probe)
    return probe


def run_live_website_probe(
    db: Session,
    candidate_id: str,
    *,
    provider: WebsiteProbeProvider | None = None,
) -> WebsiteProbe:
    candidate = db.get(LeadCandidate, candidate_id)
    if candidate is None:
        raise LeadCandidateNotFoundError(f"Lead candidate not found: {candidate_id}")

    promotion = _get_latest_promotion_decision(db, candidate_id)
    result = (provider or HttpWebsiteProbeProvider()).probe(candidate)
    evidence = dict(result.evidence or {})
    if promotion:
        evidence["promotion_status"] = promotion.status.value
        evidence["promotion_decision_id"] = promotion.id
    result = WebsiteProbeResult(
        url=result.url,
        normalized_domain=result.normalized_domain,
        status=result.status,
        http_status=result.http_status,
        has_homepage_signal=result.has_homepage_signal,
        has_impressum_signal=result.has_impressum_signal,
        has_login_signal=result.has_login_signal,
        has_shop_signal=result.has_shop_signal,
        has_booking_signal=result.has_booking_signal,
        has_checkout_signal=result.has_checkout_signal,
        has_b2c_transaction_signal=result.has_b2c_transaction_signal,
        evidence=evidence,
        confidence_score=result.confidence_score,
    )

    probe = _probe_from_result(candidate_id, promotion, result)
    db.add(probe)
    db.commit()
    db.refresh(probe)
    return probe


def get_latest_website_probe(db: Session, candidate_id: str) -> WebsiteProbe | None:
    candidate = db.get(LeadCandidate, candidate_id)
    if candidate is None:
        raise LeadCandidateNotFoundError(f"Lead candidate not found: {candidate_id}")

    return (
        db.query(WebsiteProbe)
        .filter(WebsiteProbe.lead_candidate_id == candidate_id)
        .order_by(WebsiteProbe.created_at.desc(), WebsiteProbe.id.desc())
        .first()
    )


def _get_latest_promotion_decision(
    db: Session, candidate_id: str
) -> PromotionDecision | None:
    return (
        db.query(PromotionDecision)
        .filter(PromotionDecision.lead_candidate_id == candidate_id)
        .order_by(PromotionDecision.created_at.desc(), PromotionDecision.id.desc())
        .first()
    )


def _find_existing_probe(
    db: Session,
    candidate_id: str,
    promotion: PromotionDecision | None,
    result: WebsiteProbeResult,
) -> WebsiteProbe | None:
    return (
        db.query(WebsiteProbe)
        .filter(
            WebsiteProbe.lead_candidate_id == candidate_id,
            WebsiteProbe.promotion_decision_id == (promotion.id if promotion else None),
            WebsiteProbe.normalized_domain == result.normalized_domain,
            WebsiteProbe.status == WebsiteProbeStatus(result.status),
        )
        .first()
    )


def _probe_from_result(
    candidate_id: str,
    promotion: PromotionDecision | None,
    result: WebsiteProbeResult,
) -> WebsiteProbe:
    return WebsiteProbe(
        lead_candidate_id=candidate_id,
        promotion_decision_id=promotion.id if promotion else None,
        url=result.url,
        normalized_domain=result.normalized_domain,
        status=WebsiteProbeStatus(result.status),
        http_status=result.http_status,
        has_homepage_signal=result.has_homepage_signal,
        has_impressum_signal=result.has_impressum_signal,
        has_login_signal=result.has_login_signal,
        has_shop_signal=result.has_shop_signal,
        has_booking_signal=result.has_booking_signal,
        has_checkout_signal=result.has_checkout_signal,
        has_b2c_transaction_signal=result.has_b2c_transaction_signal,
        evidence=result.evidence or {},
        confidence_score=result.confidence_score,
    )


__all__ = [
    "get_latest_website_probe",
    "run_live_website_probe",
    "run_mock_website_probe",
]
