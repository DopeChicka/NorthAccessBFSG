import json
import socket

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models import (  # noqa: F401
    CompanyEnrichment,
    CompanyQualification,
    DiscoveryRun,
    DiscoveryRunStatus,
    Lead,
    LeadCandidate,
    PromotionDecision,
    PromotionDecisionStatus,
    Scan,
    ScanReadinessDecision,
    WebsiteProbe,
    WebsiteProbeStatus,
)
from app.services.company_qualification_service import LeadCandidateNotFoundError
from app.services.scan_readiness_service import (
    ScanReadinessNotReadyError,
    create_scan_skeleton_for_candidate,
    evaluate_candidate_for_scan_readiness,
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
    domain: str | None = "https://shop.example",
) -> LeadCandidate:
    discovery_run = _create_run(db_session)
    candidate = LeadCandidate(
        discovery_run_id=discovery_run.id,
        source="google_places",
        source_reference="places/seed",
        company_name="Seed Candidate GmbH",
        domain=domain,
        city="Lübeck",
        postal_code="23552",
        category="store",
        raw_data={},
    )
    db_session.add(candidate)
    db_session.commit()
    db_session.refresh(candidate)
    return candidate


def _add_promotion(
    db_session: Session,
    candidate: LeadCandidate,
    *,
    status: PromotionDecisionStatus = PromotionDecisionStatus.ready_for_website_probe,
) -> PromotionDecision:
    promotion = PromotionDecision(
        lead_candidate_id=candidate.id,
        status=status,
        reason_code="test_reason",
        reasons={"test": True, "no_legal_conclusion": True},
        confidence_score=0.6,
    )
    db_session.add(promotion)
    db_session.commit()
    db_session.refresh(promotion)
    return promotion


def _add_website_probe(
    db_session: Session,
    candidate: LeadCandidate,
    *,
    status: WebsiteProbeStatus = WebsiteProbeStatus.reachable,
    url: str | None = "https://shop.example",
    normalized_domain: str | None = "shop.example",
    has_b2c_transaction_signal: bool | None = True,
) -> WebsiteProbe:
    probe = WebsiteProbe(
        lead_candidate_id=candidate.id,
        url=url,
        normalized_domain=normalized_domain,
        status=status,
        http_status=200 if status == WebsiteProbeStatus.reachable else None,
        has_homepage_signal=status == WebsiteProbeStatus.reachable,
        has_b2c_transaction_signal=has_b2c_transaction_signal,
        evidence={"test": True, "no_legal_conclusion": True},
        confidence_score=0.7,
    )
    db_session.add(probe)
    db_session.commit()
    db_session.refresh(probe)
    return probe


def test_unknown_candidate_fails_clearly(db_session: Session) -> None:
    with pytest.raises(LeadCandidateNotFoundError, match="Lead candidate not found"):
        evaluate_candidate_for_scan_readiness(db_session, "missing")


def test_rejected_if_no_website_probe_exists(db_session: Session) -> None:
    candidate = _create_candidate(db_session)
    _add_promotion(db_session, candidate)

    decision = evaluate_candidate_for_scan_readiness(db_session, candidate.id)

    assert decision.status.value == "rejected"
    assert decision.reason_code == "missing_website_probe"
    assert decision.website_probe_id is None
    assert decision.reasons["no_legal_conclusion"] is True


def test_needs_review_if_website_probe_missing_domain(db_session: Session) -> None:
    candidate = _create_candidate(db_session, domain=None)
    _add_promotion(db_session, candidate)
    _add_website_probe(
        db_session,
        candidate,
        status=WebsiteProbeStatus.skipped,
        url=None,
        normalized_domain=None,
        has_b2c_transaction_signal=None,
    )

    decision = evaluate_candidate_for_scan_readiness(db_session, candidate.id)

    assert decision.status.value == "needs_review"
    assert decision.reason_code == "missing_domain"
    assert decision.reasons["website_probe_has_domain"] is False


def test_needs_review_if_website_probe_missing_transaction_signal(
    db_session: Session,
) -> None:
    candidate = _create_candidate(db_session)
    _add_promotion(db_session, candidate)
    _add_website_probe(db_session, candidate, has_b2c_transaction_signal=False)

    decision = evaluate_candidate_for_scan_readiness(db_session, candidate.id)

    assert decision.status.value == "needs_review"
    assert decision.reason_code == "missing_b2c_transaction_signal"
    assert decision.reasons["b2c_transaction_signal"] is False


def test_ready_for_scan_if_probe_reachable_with_b2c_transaction_signal(
    db_session: Session,
) -> None:
    candidate = _create_candidate(db_session)
    promotion = _add_promotion(db_session, candidate)
    probe = _add_website_probe(db_session, candidate)

    decision = evaluate_candidate_for_scan_readiness(db_session, candidate.id)

    assert decision.status.value == "ready_for_scan"
    assert decision.reason_code == "ready_for_scan"
    assert decision.promotion_decision_id == promotion.id
    assert decision.website_probe_id == probe.id
    assert decision.reasons["website_probe_reachable"] is True
    assert decision.reasons["b2c_transaction_signal"] is True


def test_creating_scan_requires_ready_for_scan(db_session: Session) -> None:
    candidate = _create_candidate(db_session)
    _add_promotion(db_session, candidate)
    evaluate_candidate_for_scan_readiness(db_session, candidate.id)

    with pytest.raises(ScanReadinessNotReadyError, match="not ready for scan"):
        create_scan_skeleton_for_candidate(db_session, candidate.id)


def test_creating_scan_skeleton_works_for_ready_candidate(db_session: Session) -> None:
    candidate = _create_candidate(db_session)
    _add_promotion(db_session, candidate)
    _add_website_probe(db_session, candidate)
    decision = evaluate_candidate_for_scan_readiness(db_session, candidate.id)

    scan = create_scan_skeleton_for_candidate(db_session, candidate.id)

    assert scan.status.value == "pending"
    assert scan.lead_id
    assert scan.evidence_metadata["source"] == "scan_job_skeleton"
    assert scan.evidence_metadata["lead_candidate_id"] == candidate.id
    assert scan.evidence_metadata["scan_readiness_decision_id"] == decision.id
    assert scan.evidence_metadata["no_legal_conclusion"] is True


def test_scan_readiness_has_no_forbidden_legal_claims(db_session: Session) -> None:
    candidate = _create_candidate(db_session)
    _add_promotion(db_session, candidate)
    _add_website_probe(db_session, candidate)

    decision = evaluate_candidate_for_scan_readiness(db_session, candidate.id)
    text = json.dumps(
        {"reason_code": decision.reason_code, "reasons": decision.reasons},
        sort_keys=True,
    ).casefold()

    assert "legally obligated" not in text
    assert "violation" not in text
    assert "violates" not in text
    assert decision.reasons["no_legal_conclusion"] is True


def test_scan_readiness_makes_no_external_network_calls(
    monkeypatch,
    db_session: Session,
) -> None:
    def fail_network(*args, **kwargs):
        raise AssertionError("network access is not allowed in scan readiness")

    monkeypatch.setattr(socket, "create_connection", fail_network)
    candidate = _create_candidate(db_session)
    _add_promotion(db_session, candidate)
    _add_website_probe(db_session, candidate)

    decision = evaluate_candidate_for_scan_readiness(db_session, candidate.id)
    scan = create_scan_skeleton_for_candidate(db_session, candidate.id)

    assert decision.status.value == "ready_for_scan"
    assert scan.status.value == "pending"
