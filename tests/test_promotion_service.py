import json
import socket

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models import (  # noqa: F401
    CompanyEnrichment,
    CompanyQualification,
    CompanyQualificationStatus,
    DiscoveryRun,
    DiscoveryRunStatus,
    LeadCandidate,
    PromotionDecision,
)
from app.services.company_qualification_service import LeadCandidateNotFoundError
from app.services.promotion_service import evaluate_candidate_for_promotion


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
    raw_data: dict | None = None,
) -> LeadCandidate:
    discovery_run = _create_run(db_session)
    candidate = LeadCandidate(
        discovery_run_id=discovery_run.id,
        source=source,
        source_reference="places/seed",
        company_name="Seed Candidate GmbH",
        domain=domain,
        city="Lübeck",
        postal_code="23552",
        category=category,
        raw_data=raw_data or {},
    )
    db_session.add(candidate)
    db_session.commit()
    db_session.refresh(candidate)
    return candidate


def _add_qualification(
    db_session: Session,
    candidate: LeadCandidate,
    *,
    status: CompanyQualificationStatus,
    is_microenterprise: bool | None = None,
    website_signal: bool | None = None,
    b2c_signal: bool | None = None,
    bfsg_category_signal: str | None = None,
) -> CompanyQualification:
    qualification = CompanyQualification(
        lead_candidate_id=candidate.id,
        status=status,
        company_name=candidate.company_name,
        is_microenterprise=is_microenterprise,
        b2c_signal=b2c_signal,
        bfsg_category_signal=bfsg_category_signal,
        website_signal=website_signal,
        confidence_score=0.6,
        evidence={"test": True},
    )
    db_session.add(qualification)
    db_session.commit()
    db_session.refresh(qualification)
    return qualification


def test_unknown_candidate_fails_clearly(db_session: Session) -> None:
    with pytest.raises(LeadCandidateNotFoundError, match="Lead candidate not found: missing"):
        evaluate_candidate_for_promotion(db_session, "missing")


def test_mock_candidate_results_in_needs_review(db_session: Session) -> None:
    candidate = _create_candidate(db_session, source="mock", raw_data={"mock": True})

    decision = evaluate_candidate_for_promotion(db_session, candidate.id)

    assert decision.status.value == "needs_review"
    assert decision.reason_code == "mock_or_test_data"
    assert decision.confidence_score == 0.2
    assert decision.reasons["no_legal_conclusion"] is True


def test_missing_qualification_results_in_missing_company_data(db_session: Session) -> None:
    candidate = _create_candidate(db_session)

    decision = evaluate_candidate_for_promotion(db_session, candidate.id)

    assert decision.status.value == "needs_review"
    assert decision.reason_code == "missing_company_data"
    assert decision.company_qualification_id is None


def test_likely_not_applicable_qualification_results_in_rejected(db_session: Session) -> None:
    candidate = _create_candidate(db_session)
    qualification = _add_qualification(
        db_session,
        candidate,
        status=CompanyQualificationStatus.likely_not_applicable,
        is_microenterprise=True,
    )

    decision = evaluate_candidate_for_promotion(db_session, candidate.id)

    assert decision.status.value == "rejected"
    assert decision.reason_code == "likely_microenterprise"
    assert decision.company_qualification_id == qualification.id


def test_possible_candidate_with_domain_is_ready_for_website_probe(db_session: Session) -> None:
    candidate = _create_candidate(db_session, domain="https://seed.example")
    _add_qualification(
        db_session,
        candidate,
        status=CompanyQualificationStatus.possible_bfsg_candidate,
        is_microenterprise=False,
        website_signal=True,
        b2c_signal=True,
        bfsg_category_signal="store",
    )

    decision = evaluate_candidate_for_promotion(db_session, candidate.id)

    assert decision.status.value == "ready_for_website_probe"
    assert decision.reason_code == "possible_bfsg_candidate"
    assert decision.reasons["has_domain"] is True


def test_possible_candidate_without_website_needs_review(db_session: Session) -> None:
    candidate = _create_candidate(db_session, domain=None)
    _add_qualification(
        db_session,
        candidate,
        status=CompanyQualificationStatus.possible_bfsg_candidate,
        is_microenterprise=False,
        website_signal=False,
        b2c_signal=True,
        bfsg_category_signal="store",
    )

    decision = evaluate_candidate_for_promotion(db_session, candidate.id)

    assert decision.status.value == "needs_review"
    assert decision.reason_code == "missing_website"
    assert decision.reasons["website_signal"] is False


def test_reason_fields_do_not_contain_forbidden_legal_claims(db_session: Session) -> None:
    candidate = _create_candidate(db_session, source="mock", raw_data={"mock": True})

    decision = evaluate_candidate_for_promotion(db_session, candidate.id)
    reason_text = json.dumps(
        {"reason_code": decision.reason_code, "reasons": decision.reasons},
        sort_keys=True,
    ).casefold()

    assert "legally obligated" not in reason_text
    assert "violation" not in reason_text
    assert "violates" not in reason_text


def test_promotion_gate_makes_no_external_network_calls(monkeypatch, db_session: Session) -> None:
    def fail_network(*args, **kwargs):
        raise AssertionError("network access is not allowed in promotion gate")

    monkeypatch.setattr(socket, "create_connection", fail_network)
    candidate = _create_candidate(db_session)

    decision = evaluate_candidate_for_promotion(db_session, candidate.id)

    assert decision.status.value == "needs_review"
