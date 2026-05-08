import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models import (  # noqa: F401
    CompanyEnrichment,
    CompanyQualification,
    DiscoveryRun,
    DiscoveryRunStatus,
    LeadCandidate,
)
from app.services.company_enrichment_service import enrich_candidate_with_mock
from app.services.company_qualification_service import (
    MicroenterpriseThresholds,
    create_candidate_precheck,
    evaluate_microenterprise_signal,
    precheck_candidate,
)


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


def _create_run(db_session: Session) -> DiscoveryRun:
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
    return discovery_run


def _create_candidate(
    db_session: Session,
    *,
    source: str = "google_places",
    domain: str | None = "https://seed.example",
    category: str | None = "store",
    profile: str | None = None,
) -> LeadCandidate:
    discovery_run = _create_run(db_session)
    raw_data = {"mock_company_profile": profile} if profile else {}
    candidate = LeadCandidate(
        discovery_run_id=discovery_run.id,
        source=source,
        source_reference="places/seed",
        company_name="Seed Candidate GmbH",
        domain=domain,
        city="Lübeck",
        postal_code="23552",
        category=category,
        raw_data=raw_data,
    )
    db_session.add(candidate)
    db_session.commit()
    db_session.refresh(candidate)
    return candidate


def test_precheck_candidate_with_missing_company_data_needs_company_data(
    db_session: Session,
) -> None:
    candidate = _create_candidate(db_session, profile=None)

    qualification = create_candidate_precheck(db_session, candidate.id)

    assert qualification.status.value == "needs_company_data"
    assert qualification.is_microenterprise is None
    assert qualification.evidence["requires_company_enrichment"] is True
    assert qualification.evidence["uses_external_company_data"] is False


def test_mock_candidate_precheck_does_not_create_legal_conclusion(db_session: Session) -> None:
    discovery_run = _create_run(db_session)
    candidate = LeadCandidate(
        discovery_run_id=discovery_run.id,
        source="mock",
        source_reference="mock:luebeck:23552:ecommerce:online-shop",
        company_name="Mock Candidate Lübeck 23552 Online Shop",
        city="Lübeck",
        postal_code="23552",
        category="ecommerce",
        raw_data={"mock": True},
    )
    db_session.add(candidate)
    db_session.commit()
    db_session.refresh(candidate)

    qualification = precheck_candidate(candidate)

    assert qualification.status.value == "needs_human_review"
    assert qualification.is_microenterprise is None
    assert qualification.confidence_score == 0.1
    assert qualification.evidence["is_mock_or_test_data"] is True
    assert "legal" not in qualification.notes.casefold()


def test_qualification_precheck_uses_microenterprise_enrichment_data(
    db_session: Session,
) -> None:
    candidate = _create_candidate(db_session, profile="microenterprise")
    enrich_candidate_with_mock(db_session, candidate.id)

    qualification = create_candidate_precheck(db_session, candidate.id)

    assert qualification.is_microenterprise is True
    assert qualification.status.value == "needs_human_review"
    assert qualification.employee_count == 5
    assert qualification.annual_revenue_eur == 500_000
    assert qualification.evidence["company_enrichment_source"] == "mock_company_data"
    assert qualification.evidence["requires_company_enrichment"] is False


def test_non_microenterprise_enrichment_can_signal_possible_candidate(
    db_session: Session,
) -> None:
    candidate = _create_candidate(
        db_session,
        profile="non_microenterprise",
        domain="https://seed.example",
        category="store",
    )
    enrich_candidate_with_mock(db_session, candidate.id)

    qualification = create_candidate_precheck(db_session, candidate.id)

    assert qualification.is_microenterprise is False
    assert qualification.status.value == "possible_bfsg_candidate"
    assert qualification.employee_count == 25
    assert qualification.website_signal is True
    assert qualification.b2c_signal is True
    assert "legal" not in qualification.notes.casefold()


def test_non_microenterprise_without_category_or_website_needs_review(
    db_session: Session,
) -> None:
    candidate = _create_candidate(
        db_session,
        profile="non_microenterprise",
        domain=None,
        category=None,
    )
    enrich_candidate_with_mock(db_session, candidate.id)

    qualification = create_candidate_precheck(db_session, candidate.id)

    assert qualification.is_microenterprise is False
    assert qualification.status.value == "needs_human_review"
    assert qualification.website_signal is False
    assert qualification.b2c_signal is False


def test_microenterprise_helper_returns_true_when_all_available_values_are_below_thresholds() -> None:
    thresholds = MicroenterpriseThresholds(
        employee_count=10,
        annual_revenue_eur=2_000_000,
        balance_sheet_total_eur=2_000_000,
    )

    assert (
        evaluate_microenterprise_signal(
            employee_count=9,
            annual_revenue_eur=1_500_000,
            balance_sheet_total_eur=1_000_000,
            thresholds=thresholds,
        )
        is True
    )


def test_microenterprise_helper_returns_false_when_threshold_is_exceeded() -> None:
    thresholds = MicroenterpriseThresholds(
        employee_count=10,
        annual_revenue_eur=2_000_000,
        balance_sheet_total_eur=2_000_000,
    )

    assert (
        evaluate_microenterprise_signal(
            employee_count=10,
            annual_revenue_eur=1_000_000,
            balance_sheet_total_eur=1_000_000,
            thresholds=thresholds,
        )
        is False
    )
    assert (
        evaluate_microenterprise_signal(
            employee_count=5,
            annual_revenue_eur=2_000_001,
            balance_sheet_total_eur=None,
            thresholds=thresholds,
        )
        is False
    )


def test_microenterprise_helper_returns_none_when_required_data_is_missing() -> None:
    thresholds = MicroenterpriseThresholds(
        employee_count=10,
        annual_revenue_eur=2_000_000,
        balance_sheet_total_eur=2_000_000,
    )

    assert (
        evaluate_microenterprise_signal(
            employee_count=None,
            annual_revenue_eur=1_000_000,
            balance_sheet_total_eur=1_000_000,
            thresholds=thresholds,
        )
        is None
    )
    assert (
        evaluate_microenterprise_signal(
            employee_count=5,
            annual_revenue_eur=None,
            balance_sheet_total_eur=None,
            thresholds=thresholds,
        )
        is None
    )
