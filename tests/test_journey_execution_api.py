from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import journeys as journeys_api
from app.api.journeys import router as journeys_router
from app.db.base import Base
from app.db.session import get_db
from app.models import Finding, Journey, JourneyStatus, JourneyType, Lead, Scan, ScanStatus  # noqa: F401


def _make_client(db_session: Session) -> TestClient:
    app = FastAPI()
    app.include_router(journeys_router)
    app.dependency_overrides[get_db] = lambda: db_session
    return TestClient(app)


def test_journey_execution_endpoints(monkeypatch) -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    db_session = TestingSessionLocal()
    try:
        lead = Lead(domain="example.com", company_name="Example GmbH")
        db_session.add(lead)
        db_session.flush()
        scan = Scan(lead_id=lead.id, status=ScanStatus.pending)
        db_session.add(scan)
        db_session.flush()
        journey = Journey(
            scan_id=scan.id,
            journey_type=JourneyType.homepage,
            status=JourneyStatus.ready,
            start_url="https://example.com",
            signals={"no_legal_conclusion": True},
            evidence={"no_legal_conclusion": True},
        )
        db_session.add(journey)
        db_session.commit()
        db_session.refresh(journey)

        def fake_execute_journey_smoke(db: Session, journey_id: str) -> Journey:
            assert journey_id == journey.id
            journey.status = JourneyStatus.done
            db.commit()
            db.refresh(journey)
            return journey

        def fake_execute_scan_journeys_smoke(db: Session, scan_id: str) -> list[Journey]:
            assert scan_id == scan.id
            return [journey]

        def fake_run_axe_for_journey(db: Session, journey_id: str) -> list[Finding]:
            assert journey_id == journey.id
            finding = Finding(
                scan_id=scan.id,
                journey_id=journey.id,
                rule_id="color-contrast",
                severity="high",
                wcag_refs=[],
                evidence={"no_legal_conclusion": True},
            )
            db.add(finding)
            db.commit()
            db.refresh(finding)
            return [finding]

        def fake_run_axe_for_scan_journeys(db: Session, scan_id: str) -> list[Finding]:
            assert scan_id == scan.id
            return fake_run_axe_for_journey(db, journey.id)

        monkeypatch.setattr(
            journeys_api,
            "execute_journey_smoke",
            fake_execute_journey_smoke,
        )
        monkeypatch.setattr(
            journeys_api,
            "execute_scan_journeys_smoke",
            fake_execute_scan_journeys_smoke,
        )
        monkeypatch.setattr(
            journeys_api,
            "run_axe_for_journey",
            fake_run_axe_for_journey,
        )
        monkeypatch.setattr(
            journeys_api,
            "run_axe_for_scan_journeys",
            fake_run_axe_for_scan_journeys,
        )
        client = _make_client(db_session)

        smoke_response = client.post(f"/journeys/{journey.id}/execute-smoke")
        assert smoke_response.status_code == 200
        assert smoke_response.json()["status"] == "done"

        scan_smoke_response = client.post(f"/scans/{scan.id}/journeys/execute-smoke")
        assert scan_smoke_response.status_code == 200
        assert len(scan_smoke_response.json()["journeys"]) == 1

        axe_response = client.post(f"/journeys/{journey.id}/axe")
        assert axe_response.status_code == 200
        assert axe_response.json()["findings"][0]["journey_id"] == journey.id

        scan_axe_response = client.post(f"/scans/{scan.id}/journeys/axe")
        assert scan_axe_response.status_code == 200
        assert scan_axe_response.json()["finding_count"] == 1
    finally:
        db_session.close()
        Base.metadata.drop_all(bind=engine)
