"""Deterministic mock company-data provider.

The mock provider creates obvious test enrichment signals only. It does not call
Northdata, scrape company registers, or represent real company data.
"""

from __future__ import annotations

from app.enrichment.providers.base import CompanyEnrichmentResult
from app.models.lead_candidate import LeadCandidate

MOCK_COMPANY_SOURCE = "mock_company_data"
PROFILE_MISSING = "missing"
PROFILE_MICROENTERPRISE = "microenterprise"
PROFILE_NON_MICROENTERPRISE = "non_microenterprise"


def _profile_for_candidate(candidate: LeadCandidate) -> str:
    raw_data = candidate.raw_data or {}
    profile = raw_data.get("mock_company_profile")
    if profile in {PROFILE_MICROENTERPRISE, PROFILE_NON_MICROENTERPRISE}:
        return profile
    return PROFILE_MISSING


class MockCompanyEnrichmentProvider:
    source = MOCK_COMPANY_SOURCE

    def enrich(self, candidate: LeadCandidate) -> CompanyEnrichmentResult:
        profile = _profile_for_candidate(candidate)
        company_name = candidate.company_name
        source_reference = f"mock-company-data:{candidate.id}:{profile}"
        raw_data = {
            "provider": self.source,
            "mock": True,
            "profile": profile,
            "lead_candidate_id": candidate.id,
            "lead_candidate_source": candidate.source,
            "message": "Mock/test company-data signals only; not real register data.",
        }

        if profile == PROFILE_MICROENTERPRISE:
            return CompanyEnrichmentResult(
                source=self.source,
                source_reference=source_reference,
                company_name=company_name,
                legal_form="GmbH",
                registry_id=f"HRB-MOCK-{candidate.id[:8]}",
                source_url=f"mock://company-data/{candidate.id}",
                employee_count=5,
                annual_revenue_eur=500_000,
                balance_sheet_total_eur=400_000,
                raw_data=raw_data,
                confidence_score=0.6,
            )

        if profile == PROFILE_NON_MICROENTERPRISE:
            return CompanyEnrichmentResult(
                source=self.source,
                source_reference=source_reference,
                company_name=company_name,
                legal_form="GmbH",
                registry_id=f"HRB-MOCK-{candidate.id[:8]}",
                source_url=f"mock://company-data/{candidate.id}",
                employee_count=25,
                annual_revenue_eur=3_000_000,
                balance_sheet_total_eur=2_500_000,
                raw_data=raw_data,
                confidence_score=0.7,
            )

        return CompanyEnrichmentResult(
            source=self.source,
            source_reference=source_reference,
            company_name=company_name,
            legal_form=None,
            registry_id=None,
            source_url=None,
            employee_count=None,
            annual_revenue_eur=None,
            balance_sheet_total_eur=None,
            raw_data=raw_data,
            confidence_score=0.2,
        )


__all__ = [
    "MOCK_COMPANY_SOURCE",
    "PROFILE_MICROENTERPRISE",
    "PROFILE_MISSING",
    "PROFILE_NON_MICROENTERPRISE",
    "MockCompanyEnrichmentProvider",
]
