from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.company_enrichment import CompanyEnrichment
from app.models.company_qualification import (
    CompanyQualification,
    CompanyQualificationStatus,
)
from app.models.lead_candidate import LeadCandidate
from app.models.promotion_decision import (
    PromotionDecision,
    PromotionDecisionStatus,
    PromotionReasonCode,
)
from app.services.company_qualification_service import LeadCandidateNotFoundError


def evaluate_candidate_for_promotion(db: Session, candidate_id: str) -> PromotionDecision:
    candidate = db.get(LeadCandidate, candidate_id)
    if candidate is None:
        raise LeadCandidateNotFoundError(f"Lead candidate not found: {candidate_id}")

    qualification = _get_latest_qualification(db, candidate_id)
    enrichment = _get_latest_enrichment(db, candidate_id)
    status, reason_code, confidence_score = _decide(candidate, qualification)
    decision = PromotionDecision(
        lead_candidate_id=candidate.id,
        company_qualification_id=qualification.id if qualification else None,
        company_enrichment_id=enrichment.id if enrichment else None,
        status=status,
        reason_code=reason_code.value,
        reasons=_build_reasons(candidate, qualification, enrichment),
        confidence_score=confidence_score,
    )
    db.add(decision)
    db.commit()
    db.refresh(decision)
    return decision


def get_latest_promotion_decision(db: Session, candidate_id: str) -> PromotionDecision | None:
    candidate = db.get(LeadCandidate, candidate_id)
    if candidate is None:
        raise LeadCandidateNotFoundError(f"Lead candidate not found: {candidate_id}")

    return (
        db.query(PromotionDecision)
        .filter(PromotionDecision.lead_candidate_id == candidate_id)
        .order_by(PromotionDecision.created_at.desc(), PromotionDecision.id.desc())
        .first()
    )


def _decide(
    candidate: LeadCandidate, qualification: CompanyQualification | None
) -> tuple[PromotionDecisionStatus, PromotionReasonCode, float | None]:
    raw_data = candidate.raw_data or {}
    if candidate.source == "mock" or raw_data.get("mock") is True:
        return (
            PromotionDecisionStatus.needs_review,
            PromotionReasonCode.mock_or_test_data,
            0.2,
        )

    if qualification is None:
        return (
            PromotionDecisionStatus.needs_review,
            PromotionReasonCode.missing_company_data,
            0.2,
        )

    if qualification.status == CompanyQualificationStatus.likely_not_applicable:
        reason_code = (
            PromotionReasonCode.likely_microenterprise
            if qualification.is_microenterprise is True
            else PromotionReasonCode.insufficient_bfsg_signal
        )
        return (PromotionDecisionStatus.rejected, reason_code, qualification.confidence_score)

    if qualification.status == CompanyQualificationStatus.needs_company_data:
        return (
            PromotionDecisionStatus.needs_review,
            PromotionReasonCode.missing_company_data,
            qualification.confidence_score,
        )

    if qualification.status == CompanyQualificationStatus.needs_human_review:
        return (
            PromotionDecisionStatus.needs_review,
            PromotionReasonCode.needs_human_review,
            qualification.confidence_score,
        )

    if qualification.status == CompanyQualificationStatus.possible_bfsg_candidate:
        if candidate.domain or qualification.website_signal is True:
            return (
                PromotionDecisionStatus.ready_for_website_probe,
                PromotionReasonCode.possible_bfsg_candidate,
                qualification.confidence_score,
            )
        return (
            PromotionDecisionStatus.needs_review,
            PromotionReasonCode.missing_website,
            qualification.confidence_score,
        )

    return (
        PromotionDecisionStatus.needs_review,
        PromotionReasonCode.needs_human_review,
        qualification.confidence_score,
    )


def _build_reasons(
    candidate: LeadCandidate,
    qualification: CompanyQualification | None,
    enrichment: CompanyEnrichment | None,
) -> dict[str, object]:
    return {
        "candidate_source": candidate.source,
        "category": candidate.category,
        "has_domain": bool(candidate.domain),
        "qualification_status": qualification.status.value if qualification else None,
        "is_microenterprise": qualification.is_microenterprise if qualification else None,
        "b2c_signal": qualification.b2c_signal if qualification else None,
        "bfsg_category_signal": qualification.bfsg_category_signal if qualification else None,
        "website_signal": qualification.website_signal if qualification else None,
        "enrichment_source": enrichment.source if enrichment else None,
        "no_legal_conclusion": True,
    }


def _get_latest_qualification(db: Session, candidate_id: str) -> CompanyQualification | None:
    return (
        db.query(CompanyQualification)
        .filter(CompanyQualification.lead_candidate_id == candidate_id)
        .order_by(CompanyQualification.created_at.desc(), CompanyQualification.id.desc())
        .first()
    )


def _get_latest_enrichment(db: Session, candidate_id: str) -> CompanyEnrichment | None:
    return (
        db.query(CompanyEnrichment)
        .filter(CompanyEnrichment.lead_candidate_id == candidate_id)
        .order_by(CompanyEnrichment.created_at.desc(), CompanyEnrichment.id.desc())
        .first()
    )


__all__ = [
    "evaluate_candidate_for_promotion",
    "get_latest_promotion_decision",
]
