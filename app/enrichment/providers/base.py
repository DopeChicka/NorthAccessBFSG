"""Provider interface for company enrichment signals.

Company enrichment results are evidence/signal data only. They must not make
legal conclusions or final BFSG applicability decisions.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Protocol

from app.models.lead_candidate import LeadCandidate


@dataclass(frozen=True)
class CompanyEnrichmentResult:
    source: str
    source_reference: str | None = None
    company_name: str | None = None
    legal_form: str | None = None
    registry_id: str | None = None
    source_url: str | None = None
    employee_count: int | None = None
    annual_revenue_eur: int | None = None
    balance_sheet_total_eur: int | None = None
    raw_data: dict[str, Any] | None = None
    confidence_score: float | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["raw_data"] = self.raw_data or {}
        return data


class CompanyEnrichmentProvider(Protocol):
    source: str

    def enrich(self, candidate: LeadCandidate) -> CompanyEnrichmentResult:
        """Return company-data signals for a lead candidate."""
