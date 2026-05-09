import json
import socket

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models import (  # noqa: F401
    DiscoveryRun,
    DiscoveryRunStatus,
    Journey,
    JourneyStatus,
    JourneyType,
    Lead,
    LeadCandidate,
    Scan,
    ScanEvidence,
    ScanStatus,
    WebsiteProbe,
    WebsiteProbeStatus,
)
from app.services.journey_planning_service import (
    ScanNotFoundError,
    list_scan_journeys,
    plan_scan_journeys,
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


def _create_scan_with_candidate(
    db_session: Session,
    *,
    domain: str = "example.com",
    has_shop_signal: bool | None = None,
    has_checkout_signal: bool | None = None,
    has_b2c_transaction_signal: bool | None = None,
    has_login_signal: bool | None = None,
    has_booking_signal: bool | None = None,
) -> tuple[Scan, LeadCandidate, WebsiteProbe]:
    discovery_run = DiscoveryRun(
        city="Berlin",
        normalized_city="berlin",
        status=DiscoveryRunStatus.done,
        keyword_groups=[],
        postal_codes=[],
        query_plan=[],
    )
    db_session.add(discovery_run)
    db_session.flush()
    candidate = LeadCandidate(
        discovery_run_id=discovery_run.id,
        source="test",
        company_name="Example GmbH",
        domain=domain,
        category="shop",
        raw_data={},
    )
    db_session.add(candidate)
    db_session.flush()
    lead = Lead(domain=domain, company_name="Example GmbH")
    db_session.add(lead)
    db_session.flush()
    scan = Scan(
        lead_id=lead.id,
        status=ScanStatus.pending,
        evidence_metadata={
            "lead_candidate_id": candidate.id,
            "no_legal_conclusion": True,
        },
    )
    db_session.add(scan)
    db_session.flush()
    probe = WebsiteProbe(
        lead_candidate_id=candidate.id,
        url=f"https://{domain}",
        normalized_domain=domain,
        status=WebsiteProbeStatus.reachable,
        has_homepage_signal=True,
        has_shop_signal=has_shop_signal,
        has_checkout_signal=has_checkout_signal,
        has_b2c_transaction_signal=has_b2c_transaction_signal,
        has_login_signal=has_login_signal,
        has_booking_signal=has_booking_signal,
        evidence={"no_legal_conclusion": True},
    )
    db_session.add(probe)
    db_session.commit()
    db_session.refresh(scan)
    db_session.refresh(candidate)
    db_session.refresh(probe)
    return scan, candidate, probe


def test_plan_homepage_journey_when_scan_has_domain(db_session: Session) -> None:
    scan, _, _ = _create_scan_with_candidate(db_session)

    journeys = plan_scan_journeys(db_session, scan.id)
    homepage = _journey_by_type(journeys, JourneyType.homepage)

    assert homepage.status == JourneyStatus.ready
    assert homepage.start_url == "https://example.com"
    assert homepage.evidence["no_live_crawling"] is True
    assert homepage.evidence["no_legal_conclusion"] is True


def test_plan_shop_cart_checkout_from_probe_signals(db_session: Session) -> None:
    scan, _, _ = _create_scan_with_candidate(
        db_session,
        has_shop_signal=True,
        has_checkout_signal=True,
        has_b2c_transaction_signal=True,
    )

    journeys = plan_scan_journeys(db_session, scan.id)
    by_type = {journey.journey_type: journey for journey in journeys}

    for journey_type in (JourneyType.shop, JourneyType.cart, JourneyType.checkout):
        assert by_type[journey_type].status == JourneyStatus.ready
        assert by_type[journey_type].evidence["reason"] == "transaction_signal_detected"


def test_plan_login_journey_from_probe_signal(db_session: Session) -> None:
    scan, _, _ = _create_scan_with_candidate(db_session, has_login_signal=True)

    journeys = plan_scan_journeys(db_session, scan.id)
    login = _journey_by_type(journeys, JourneyType.login)

    assert login.status == JourneyStatus.ready
    assert login.evidence["reason"] == "login_signal_detected"


def test_no_duplicate_journeys_on_repeated_planning(db_session: Session) -> None:
    scan, _, _ = _create_scan_with_candidate(
        db_session,
        has_shop_signal=True,
        has_checkout_signal=True,
        has_b2c_transaction_signal=True,
    )

    first = plan_scan_journeys(db_session, scan.id)
    second = plan_scan_journeys(db_session, scan.id)

    assert {journey.id for journey in first} == {journey.id for journey in second}
    assert db_session.query(Journey).filter(Journey.scan_id == scan.id).count() == len(first)


def test_unknown_scan_fails_clearly(db_session: Session) -> None:
    with pytest.raises(ScanNotFoundError, match="Scan not found: missing"):
        plan_scan_journeys(db_session, "missing")

    with pytest.raises(ScanNotFoundError, match="Scan not found: missing"):
        list_scan_journeys(db_session, "missing")


def test_journey_planning_makes_no_external_calls(
    monkeypatch,
    db_session: Session,
) -> None:
    def fail_network(*args, **kwargs):
        raise AssertionError("network access is not allowed in journey tests")

    monkeypatch.setattr(socket, "create_connection", fail_network)
    scan, _, _ = _create_scan_with_candidate(db_session)

    journeys = plan_scan_journeys(db_session, scan.id)

    assert journeys


def test_journey_evidence_has_no_forbidden_legal_claims(db_session: Session) -> None:
    scan, _, _ = _create_scan_with_candidate(db_session, has_booking_signal=True)

    journeys = plan_scan_journeys(db_session, scan.id)
    text = json.dumps(
        [
            {
                "signals": journey.signals,
                "evidence": journey.evidence,
            }
            for journey in journeys
        ],
        sort_keys=True,
    ).casefold()

    assert "legally obligated" not in text
    assert "violation" not in text
    assert "violates" not in text
    assert "certified" not in text


def _journey_by_type(journeys: list[Journey], journey_type: JourneyType) -> Journey:
    return [journey for journey in journeys if journey.journey_type == journey_type][0]
