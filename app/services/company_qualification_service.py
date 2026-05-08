from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.company_enrichment import CompanyEnrichment
from app.models.company_qualification import (
    CompanyQualification,
    CompanyQualificationStatus,
)
from app.models.lead_candidate import LeadCandidate


class LeadCandidateNotFoundError(LookupError):
    pass


@dataclass(frozen=True)
class MicroenterpriseThresholds:
    employee_count: int
    annual_revenue_eur: int
    balance_sheet_total_eur: int


def get_microenterprise_thresholds() -> MicroenterpriseThresholds:
    settings = get_settings()
    return MicroenterpriseThresholds(
        employee_count=settings.bfsg_microenterprise_employee_threshold,
        annual_revenue_eur=settings.bfsg_microenterprise_revenue_threshold_eur,
        balance_sheet_total_eur=settings.bfsg_microenterprise_balance_threshold_eur,
    )


def evaluate_microenterprise_signal(
    *,
    employee_count: int | None,
    annual_revenue_eur: int | None,
    balance_sheet_total_eur: int | None,
    thresholds: MicroenterpriseThresholds | None = None,
) -> bool | None:
    thresholds = thresholds or get_microenterprise_thresholds()
    financial_values = [
        value for value in (annual_revenue_eur, balance_sheet_total_eur) if value is not None
    ]
    if employee_count is None or not financial_values:
        return None
    if employee_count >= thresholds.employee_count:
        return False
    if annual_revenue_eur is not None and annual_revenue_eur > thresholds.annual_revenue_eur:
        return False
    if (
        balance_sheet_total_eur is not None
        and balance_sheet_total_eur > thresholds.balance_sheet_total_eur
    ):
        return False
    return True


def create_candidate_precheck(db: Session, candidate_id: str) -> CompanyQualification:
    candidate = db.get(LeadCandidate, candidate_id)
    if candidate is None:
        raise LeadCandidateNotFoundError(f"Lead candidate not found: {candidate_id}")

    qualification = precheck_candidate(
        candidate,
        enrichment=_get_latest_enrichment_for_candidate(db, candidate_id),
    )
    db.add(qualification)
    db.commit()
    db.refresh(qualification)
    return qualification


def get_latest_candidate_qualification(
    db: Session, candidate_id: str
) -> CompanyQualification | None:
    candidate = db.get(LeadCandidate, candidate_id)
    if candidate is None:
        raise LeadCandidateNotFoundError(f"Lead candidate not found: {candidate_id}")

    return (
        db.query(CompanyQualification)
        .filter(CompanyQualification.lead_candidate_id == candidate_id)
        .order_by(CompanyQualification.created_at.desc(), CompanyQualification.id.desc())
        .first()
    )


def precheck_candidate(
    candidate: LeadCandidate, enrichment: CompanyEnrichment | None = None
) -> CompanyQualification:
    candidate_raw_data = candidate.raw_data or {}
    enrichment_raw_data = enrichment.raw_data if enrichment else {}
    employee_count = _int_or_none(
        enrichment.employee_count if enrichment else candidate_raw_data.get("employee_count")
    )
    annual_revenue_eur = _int_or_none(
        enrichment.annual_revenue_eur
        if enrichment
        else candidate_raw_data.get("annual_revenue_eur")
    )
    balance_sheet_total_eur = _int_or_none(
        enrichment.balance_sheet_total_eur
        if enrichment
        else candidate_raw_data.get("balance_sheet_total_eur")
    )
    is_microenterprise = evaluate_microenterprise_signal(
        employee_count=employee_count,
        annual_revenue_eur=annual_revenue_eur,
        balance_sheet_total_eur=balance_sheet_total_eur,
    )
    is_mock = (
        candidate.source == "mock"
        or candidate_raw_data.get("mock") is True
        or enrichment_raw_data.get("mock") is True
    )
    company_name = enrichment.company_name if enrichment else candidate.company_name
    website_signal = bool(candidate.domain)
    b2c_signal = bool(candidate.category)
    category_signal = candidate.category

    status = CompanyQualificationStatus.needs_company_data
    confidence_score = 0.3
    notes = "Company enrichment is required before this candidate can be treated as qualified."

    if is_mock and is_microenterprise is None:
        status = CompanyQualificationStatus.needs_human_review
        confidence_score = 0.1
        notes = "Mock/test candidate; never treat as a real company qualification."
    elif not company_name:
        status = CompanyQualificationStatus.needs_company_data
        confidence_score = 0.2
    elif is_microenterprise is None:
        status = CompanyQualificationStatus.needs_company_data
        confidence_score = 0.35 if enrichment else 0.3
    elif is_microenterprise is True:
        status = (
            CompanyQualificationStatus.needs_human_review
            if is_mock
            else CompanyQualificationStatus.likely_not_applicable
        )
        confidence_score = 0.5 if is_mock else 0.6
        notes = "Microenterprise signal present; human review is still required before exclusion."
    elif b2c_signal and category_signal and website_signal:
        status = CompanyQualificationStatus.possible_bfsg_candidate
        confidence_score = 0.65 if enrichment else 0.5
        notes = "Company-size and candidate signals are present; human review remains required."
    else:
        status = CompanyQualificationStatus.needs_human_review
        confidence_score = 0.5
        notes = "Company-size signal is present, but category or website signals need review."

    evidence: dict[str, Any] = {
        "source": candidate.source,
        "source_reference": candidate.source_reference,
        "is_seed_candidate": True,
        "requires_company_enrichment": enrichment is None,
        "uses_external_company_data": False,
        "is_mock_or_test_data": is_mock,
        "has_company_name": bool(company_name),
        "has_city": bool(candidate.city),
        "has_category": bool(candidate.category),
        "has_website": website_signal,
        "has_employee_count": employee_count is not None,
        "has_annual_revenue_eur": annual_revenue_eur is not None,
        "has_balance_sheet_total_eur": balance_sheet_total_eur is not None,
        "company_enrichment_id": enrichment.id if enrichment else None,
        "company_enrichment_source": enrichment.source if enrichment else None,
        "company_enrichment_is_mock": enrichment_raw_data.get("mock") is True,
    }

    return CompanyQualification(
        lead_candidate_id=candidate.id,
        status=status,
        company_name=company_name,
        legal_form=enrichment.legal_form if enrichment else None,
        registry_id=enrichment.registry_id if enrichment else None,
        northdata_url=enrichment.source_url if enrichment else None,
        employee_count=employee_count,
        annual_revenue_eur=annual_revenue_eur,
        balance_sheet_total_eur=balance_sheet_total_eur,
        is_microenterprise=is_microenterprise,
        b2c_signal=b2c_signal,
        bfsg_category_signal=category_signal,
        website_signal=website_signal,
        confidence_score=confidence_score,
        evidence=evidence,
        notes=notes,
    )


def _get_latest_enrichment_for_candidate(
    db: Session, candidate_id: str
) -> CompanyEnrichment | None:
    return (
        db.query(CompanyEnrichment)
        .filter(CompanyEnrichment.lead_candidate_id == candidate_id)
        .order_by(CompanyEnrichment.created_at.desc(), CompanyEnrichment.id.desc())
        .first()
    )


def _int_or_none(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


__all__ = [
    "LeadCandidateNotFoundError",
    "MicroenterpriseThresholds",
    "create_candidate_precheck",
    "evaluate_microenterprise_signal",
    "get_latest_candidate_qualification",
    "precheck_candidate",
]
