import json
import socket
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models import (  # noqa: F401
    Finding,
    Journey,
    JourneyStatus,
    JourneyType,
    Lead,
    Report,
    Scan,
    ScanEvidence,
    ScanStatus,
)
from app.services.axe_homepage_service import AxeHomepageResult, AxeViolation
from app.services.axe_journey_service import (
    AxeJourneyAuditError,
    run_axe_for_journey,
    run_axe_for_scan_journeys,
)
from app.services.browser_smoke_service import BrowserSmokeResult
from app.services.journey_execution_service import (
    JourneyExecutionError,
    execute_journey_smoke,
    execute_scan_journeys_smoke,
)
from app.services.report_service import generate_scan_json_report


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


def _create_scan(db_session: Session) -> Scan:
    lead = Lead(domain="example.com", company_name="Example GmbH")
    db_session.add(lead)
    db_session.flush()
    scan = Scan(
        lead_id=lead.id,
        status=ScanStatus.pending,
        evidence_metadata={"no_legal_conclusion": True},
    )
    db_session.add(scan)
    db_session.commit()
    db_session.refresh(scan)
    return scan


def _create_journey(
    db_session: Session,
    scan: Scan,
    *,
    journey_type: JourneyType = JourneyType.homepage,
    start_url: str | None = "https://example.com",
    status: JourneyStatus = JourneyStatus.ready,
) -> Journey:
    journey = Journey(
        scan_id=scan.id,
        journey_type=journey_type,
        status=status,
        start_url=start_url,
        detected_url=None,
        signals={"no_legal_conclusion": True},
        evidence={"source": "test", "no_legal_conclusion": True},
    )
    db_session.add(journey)
    db_session.commit()
    db_session.refresh(journey)
    return journey


def _fake_smoke_runner(url: str) -> BrowserSmokeResult:
    return BrowserSmokeResult(
        target_url=url,
        final_url=f"{url}/final",
        page_title="Journey Page",
        http_status=200,
        captured_at=datetime.now(UTC).isoformat(),
    )


def _fake_axe_runner(url: str) -> AxeHomepageResult:
    return AxeHomepageResult(
        target_url=url,
        final_url=f"{url}/axe-final",
        page_title="Axe Journey Page",
        http_status=200,
        captured_at=datetime.now(UTC).isoformat(),
        violations=[
            AxeViolation(
                rule_id="color-contrast",
                impact="serious",
                description="Elements must meet contrast requirements",
                help_url="https://dequeuniversity.com/rules/axe/color-contrast",
                wcag_refs=["wcag143"],
                nodes=[{"target": [".button"]}],
            )
        ],
    )


def test_execute_one_journey_smoke_with_mocked_runner(db_session: Session) -> None:
    scan = _create_scan(db_session)
    journey = _create_journey(db_session, scan)

    executed = execute_journey_smoke(db_session, journey.id, runner=_fake_smoke_runner)
    evidence = db_session.query(ScanEvidence).filter_by(scan_id=scan.id).one()

    assert executed.status == JourneyStatus.done
    assert executed.executed_at is not None
    assert executed.detected_url == "https://example.com/final"
    assert evidence.evidence_type == "journey_smoke"
    assert evidence.related_entity_type == "journey"
    assert evidence.related_entity_id == journey.id
    assert evidence.evidence_metadata["journey_type"] == "homepage"
    assert evidence.evidence_metadata["no_legal_conclusion"] is True


def test_execute_scan_journeys_smoke(db_session: Session) -> None:
    scan = _create_scan(db_session)
    first = _create_journey(db_session, scan, journey_type=JourneyType.homepage)
    second = _create_journey(db_session, scan, journey_type=JourneyType.login)

    journeys = execute_scan_journeys_smoke(
        db_session, scan.id, runner=_fake_smoke_runner
    )

    assert {journey.id for journey in journeys} == {first.id, second.id}
    assert all(journey.status == JourneyStatus.done for journey in journeys)
    assert db_session.query(ScanEvidence).filter_by(evidence_type="journey_smoke").count() == 2


def test_journey_with_no_url_fails_clearly(db_session: Session) -> None:
    scan = _create_scan(db_session)
    journey = _create_journey(db_session, scan, start_url=None)

    with pytest.raises(JourneyExecutionError, match="Journey has no URL"):
        execute_journey_smoke(db_session, journey.id, runner=_fake_smoke_runner)

    db_session.refresh(journey)
    assert journey.status == JourneyStatus.failed

    with pytest.raises(AxeJourneyAuditError, match="Journey has no URL"):
        run_axe_for_journey(db_session, journey.id, runner=_fake_axe_runner)


def test_axe_per_journey_creates_finding_with_journey_id(
    db_session: Session,
) -> None:
    scan = _create_scan(db_session)
    journey = _create_journey(db_session, scan)

    findings = run_axe_for_journey(db_session, journey.id, runner=_fake_axe_runner)
    evidence = db_session.query(ScanEvidence).filter_by(evidence_type="axe_journey").one()

    assert len(findings) == 1
    assert findings[0].journey_id == journey.id
    assert findings[0].severity == "high"
    assert findings[0].evidence["journey_type"] == "homepage"
    assert evidence.related_entity_type == "journey"
    assert evidence.related_entity_id == journey.id
    assert evidence.evidence_metadata["findings_count"] == 1


def test_scan_level_axe_per_journeys_aggregates_findings(db_session: Session) -> None:
    scan = _create_scan(db_session)
    first = _create_journey(db_session, scan, journey_type=JourneyType.homepage)
    second = _create_journey(db_session, scan, journey_type=JourneyType.login)

    findings = run_axe_for_scan_journeys(db_session, scan.id, runner=_fake_axe_runner)

    assert len(findings) == 2
    assert {finding.journey_id for finding in findings} == {first.id, second.id}


def test_report_includes_journey_statuses_and_finding_journey_id(
    db_session: Session,
) -> None:
    scan = _create_scan(db_session)
    journey = _create_journey(db_session, scan)
    execute_journey_smoke(db_session, journey.id, runner=_fake_smoke_runner)
    findings = run_axe_for_journey(db_session, journey.id, runner=_fake_axe_runner)

    report = generate_scan_json_report(db_session, scan.id)

    assert report.output["journeys"][0]["status"] == "done"
    assert report.output["journeys"][0]["executed_at"] is not None
    assert report.output["findings"][0]["journey_id"] == findings[0].journey_id


def test_journey_execution_makes_no_external_calls(
    monkeypatch,
    db_session: Session,
) -> None:
    def fail_network(*args, **kwargs):
        raise AssertionError("network access is not allowed in journey execution tests")

    monkeypatch.setattr(socket, "create_connection", fail_network)
    scan = _create_scan(db_session)
    journey = _create_journey(db_session, scan)

    execute_journey_smoke(db_session, journey.id, runner=_fake_smoke_runner)
    findings = run_axe_for_journey(db_session, journey.id, runner=_fake_axe_runner)

    assert len(findings) == 1


def test_journey_execution_has_no_forbidden_legal_claims(db_session: Session) -> None:
    scan = _create_scan(db_session)
    journey = _create_journey(db_session, scan)

    execute_journey_smoke(db_session, journey.id, runner=_fake_smoke_runner)
    run_axe_for_journey(db_session, journey.id, runner=_fake_axe_runner)
    payload = {
        "journey": {
            "evidence": journey.evidence,
            "signals": journey.signals,
        },
        "evidence": [
            row.evidence_metadata
            for row in db_session.query(ScanEvidence).filter_by(scan_id=scan.id).all()
        ],
        "findings": [
            finding.evidence
            for finding in db_session.query(Finding).filter_by(scan_id=scan.id).all()
        ],
    }
    text = json.dumps(payload, sort_keys=True).casefold()

    assert "legally obligated" not in text
    assert "violation" not in text
    assert "violates" not in text
    assert "certified" not in text
