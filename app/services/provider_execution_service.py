from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.discovery.providers.base import DiscoveryProvider, ProviderResult
from app.discovery.providers.google_places_provider import GooglePlacesProvider
from app.discovery.providers.mock_provider import MockDiscoveryProvider
from app.models.lead_candidate import LeadCandidate
from app.services.discovery_service import DiscoveryRunNotFoundError, get_discovery_run


@dataclass(frozen=True)
class ProviderExecutionSummary:
    discovery_run_id: str
    provider: str
    candidates_created: int
    candidates_total: int

    def to_dict(self) -> dict[str, str | int]:
        return {
            "discovery_run_id": self.discovery_run_id,
            "provider": self.provider,
            "candidates_created": self.candidates_created,
            "candidates_total": self.candidates_total,
        }


def execute_mock_provider(db: Session, discovery_run_id: str) -> ProviderExecutionSummary:
    return execute_provider(db, discovery_run_id, MockDiscoveryProvider())


def execute_google_places_provider(
    db: Session, discovery_run_id: str
) -> ProviderExecutionSummary:
    return execute_provider(db, discovery_run_id, GooglePlacesProvider())


def execute_provider(
    db: Session, discovery_run_id: str, provider: DiscoveryProvider
) -> ProviderExecutionSummary:
    discovery_run = get_discovery_run(db, discovery_run_id)
    results = provider.search(discovery_run.query_plan)

    candidates_created = 0
    for result in results:
        if result.source_reference and _candidate_exists(db, discovery_run_id, result):
            continue

        db.add(_candidate_from_provider_result(discovery_run_id, result))
        candidates_created += 1

    db.commit()
    candidates_total = (
        db.query(LeadCandidate)
        .filter(
            LeadCandidate.discovery_run_id == discovery_run_id,
            LeadCandidate.source == provider.source,
        )
        .count()
    )
    return ProviderExecutionSummary(
        discovery_run_id=discovery_run_id,
        provider=provider.source,
        candidates_created=candidates_created,
        candidates_total=candidates_total,
    )


def _candidate_exists(db: Session, discovery_run_id: str, result: ProviderResult) -> bool:
    return (
        db.query(LeadCandidate.id)
        .filter(
            LeadCandidate.discovery_run_id == discovery_run_id,
            LeadCandidate.source == result.source,
            LeadCandidate.source_reference == result.source_reference,
        )
        .first()
        is not None
    )


def _candidate_from_provider_result(
    discovery_run_id: str, result: ProviderResult
) -> LeadCandidate:
    return LeadCandidate(
        discovery_run_id=discovery_run_id,
        source=result.source,
        source_reference=result.source_reference,
        company_name=result.company_name,
        domain=result.domain,
        city=result.city,
        postal_code=result.postal_code,
        address=result.address,
        phone=result.phone,
        category=result.category,
        raw_data=result.raw_data or {},
        confidence_score=result.confidence_score,
    )


__all__ = [
    "DiscoveryRunNotFoundError",
    "ProviderExecutionSummary",
    "execute_google_places_provider",
    "execute_mock_provider",
    "execute_provider",
]
