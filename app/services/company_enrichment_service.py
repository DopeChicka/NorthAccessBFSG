from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.enrichment.providers.base import CompanyEnrichmentProvider, CompanyEnrichmentResult
from app.enrichment.providers.mock_company_provider import MockCompanyEnrichmentProvider
from app.models.company_enrichment import CompanyEnrichment
from app.models.lead_candidate import LeadCandidate
from app.services.company_qualification_service import LeadCandidateNotFoundError


@dataclass(frozen=True)
class CompanyEnrichmentSummary:
    candidate_id: str
    enrichment_id: str
    source: str
    confidence_score: float | None

    def to_dict(self) -> dict[str, str | float | None]:
        return {
            "candidate_id": self.candidate_id,
            "enrichment_id": self.enrichment_id,
            "source": self.source,
            "confidence_score": self.confidence_score,
        }


def enrich_candidate_with_mock(db: Session, candidate_id: str) -> CompanyEnrichmentSummary:
    return enrich_candidate(db, candidate_id, MockCompanyEnrichmentProvider())


def enrich_candidate(
    db: Session, candidate_id: str, provider: CompanyEnrichmentProvider
) -> CompanyEnrichmentSummary:
    candidate = db.get(LeadCandidate, candidate_id)
    if candidate is None:
        raise LeadCandidateNotFoundError(f"Lead candidate not found: {candidate_id}")

    result = provider.enrich(candidate)
    enrichment = _find_existing_enrichment(db, candidate_id, result)
    if enrichment is None:
        enrichment = _enrichment_from_result(candidate_id, result)
        db.add(enrichment)
        db.commit()
        db.refresh(enrichment)

    return CompanyEnrichmentSummary(
        candidate_id=candidate_id,
        enrichment_id=enrichment.id,
        source=enrichment.source,
        confidence_score=enrichment.confidence_score,
    )


def get_latest_enrichment(db: Session, candidate_id: str) -> CompanyEnrichment | None:
    candidate = db.get(LeadCandidate, candidate_id)
    if candidate is None:
        raise LeadCandidateNotFoundError(f"Lead candidate not found: {candidate_id}")

    return (
        db.query(CompanyEnrichment)
        .filter(CompanyEnrichment.lead_candidate_id == candidate_id)
        .order_by(CompanyEnrichment.created_at.desc(), CompanyEnrichment.id.desc())
        .first()
    )


def _find_existing_enrichment(
    db: Session, candidate_id: str, result: CompanyEnrichmentResult
) -> CompanyEnrichment | None:
    if not result.source_reference:
        return None
    return (
        db.query(CompanyEnrichment)
        .filter(
            CompanyEnrichment.lead_candidate_id == candidate_id,
            CompanyEnrichment.source == result.source,
            CompanyEnrichment.source_reference == result.source_reference,
        )
        .first()
    )


def _enrichment_from_result(
    candidate_id: str, result: CompanyEnrichmentResult
) -> CompanyEnrichment:
    return CompanyEnrichment(
        lead_candidate_id=candidate_id,
        source=result.source,
        source_reference=result.source_reference,
        company_name=result.company_name,
        legal_form=result.legal_form,
        registry_id=result.registry_id,
        source_url=result.source_url,
        employee_count=result.employee_count,
        annual_revenue_eur=result.annual_revenue_eur,
        balance_sheet_total_eur=result.balance_sheet_total_eur,
        raw_data=result.raw_data or {},
        confidence_score=result.confidence_score,
    )


__all__ = [
    "CompanyEnrichmentSummary",
    "enrich_candidate",
    "enrich_candidate_with_mock",
    "get_latest_enrichment",
]
