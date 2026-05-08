"""Company enrichment provider adapters."""

from app.enrichment.providers.base import (
    CompanyEnrichmentProvider,
    CompanyEnrichmentResult,
)
from app.enrichment.providers.mock_company_provider import MockCompanyEnrichmentProvider

__all__ = [
    "CompanyEnrichmentProvider",
    "CompanyEnrichmentResult",
    "MockCompanyEnrichmentProvider",
]
