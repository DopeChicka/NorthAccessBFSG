import socket

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models import CompanyEnrichment, DiscoveryRun, DiscoveryRunStatus, LeadCandidate  # noqa: F401
from app.services.company_enrichment_service import (
    enrich_candidate_with_mock,
    get_latest_enrichment,
)
from app.services.company_qualification_service import LeadCandidateNotFoundError


@pytest.fixture()
def db_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    TestingSessionLocal = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)

    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


def _create_candidate(
    db_session: Session,
    *,
    profile: str | None = None,
    domain: str | None = None,
) -> LeadCandidate:
    discovery_run = DiscoveryRun(
        city="Lübeck",
        normalized_city="luebeck",
        status=DiscoveryRunStatus.done,
        keyword_groups=[],
        postal_codes=["23552"],
        query_plan=[],
    )
    db_session.add(discovery_run)
    db_session.commit()
    db_session.refresh(discovery_run)

    raw_data = {"mock_company_profile": profile} if profile else {}
    candidate = LeadCandidate(
        discovery_run_id=discovery_run.id,
        source="google_places",
        source_reference="places/seed",
        company_name="Seed Candidate GmbH",
        domain=domain,
        city="Lübeck",
        postal_code="23552",
        category="store",
        raw_data=raw_data,
    )
    db_session.add(candidate)
    db_session.commit()
    db_session.refresh(candidate)
    return candidate


def test_mock_enrichment_persists_company_enrichment(db_session: Session) -> None:
    candidate = _create_candidate(db_session, profile="microenterprise")

    summary = enrich_candidate_with_mock(db_session, candidate.id)

    assert summary.candidate_id == candidate.id
    assert summary.source == "mock_company_data"
    assert summary.confidence_score == 0.6

    enrichment = db_session.get(CompanyEnrichment, summary.enrichment_id)
    assert enrichment is not None
    assert enrichment.lead_candidate_id == candidate.id
    assert enrichment.employee_count == 5
    assert enrichment.annual_revenue_eur == 500_000
    assert enrichment.raw_data["mock"] is True
    assert enrichment.raw_data["profile"] == "microenterprise"


def test_mock_enrichment_is_idempotent_for_same_candidate_and_profile(
    db_session: Session,
) -> None:
    candidate = _create_candidate(db_session, profile="non_microenterprise")

    first = enrich_candidate_with_mock(db_session, candidate.id)
    second = enrich_candidate_with_mock(db_session, candidate.id)

    assert first.enrichment_id == second.enrichment_id
    assert db_session.query(CompanyEnrichment).count() == 1


def test_get_latest_enrichment_returns_latest_for_candidate(db_session: Session) -> None:
    candidate = _create_candidate(db_session, profile="missing")
    summary = enrich_candidate_with_mock(db_session, candidate.id)

    enrichment = get_latest_enrichment(db_session, candidate.id)

    assert enrichment is not None
    assert enrichment.id == summary.enrichment_id
    assert enrichment.source == "mock_company_data"


def test_enrichment_unknown_candidate_fails_clearly(db_session: Session) -> None:
    with pytest.raises(LeadCandidateNotFoundError, match="Lead candidate not found: missing"):
        enrich_candidate_with_mock(db_session, "missing")


def test_mock_enrichment_makes_no_external_network_calls(monkeypatch, db_session: Session) -> None:
    def fail_network(*args, **kwargs):
        raise AssertionError("network access is not allowed in mock enrichment")

    monkeypatch.setattr(socket, "create_connection", fail_network)
    candidate = _create_candidate(db_session, profile="missing")

    summary = enrich_candidate_with_mock(db_session, candidate.id)

    assert summary.source == "mock_company_data"
