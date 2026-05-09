from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.delta import router as delta_router
from app.db.base import Base
from app.db.session import get_db
from app.models import DeltaComparison, Finding, Lead, Scan, ScanStatus  # noqa: F401


def _make_client(db_session: Session) -> TestClient:
    app = FastAPI()
    app.include_router(delta_router)
    app.dependency_overrides[get_db] = lambda: db_session
    return TestClient(app)


def _create_scan(db_session: Session) -> Scan:
    lead = Lead(domain="example.com", company_name="Example GmbH")
    db_session.add(lead)
    db_session.flush()
    scan = Scan(lead_id=lead.id, status=ScanStatus.done)
    db_session.add(scan)
    db_session.commit()
    db_session.refresh(scan)
    return scan


def _create_finding(db_session: Session, scan: Scan, rule_id: str) -> None:
    db_session.add(
        Finding(
            scan_id=scan.id,
            rule_id=rule_id,
            severity="high",
            description="Technical signal for review",
            wcag_refs=[],
            evidence={"sample_targets": [[".target"]], "no_legal_conclusion": True},
        )
    )
    db_session.commit()


def test_delta_api_create_get_and_list() -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    db_session = TestingSessionLocal()
    try:
        baseline = _create_scan(db_session)
        target = _create_scan(db_session)
        _create_finding(db_session, baseline, "color-contrast")
        _create_finding(db_session, target, "label")
        client = _make_client(db_session)

        create_response = client.post(f"/scans/{target.id}/delta/{baseline.id}")
        assert create_response.status_code == 200
        created = create_response.json()
        assert created["baseline_scan_id"] == baseline.id
        assert created["target_scan_id"] == target.id
        assert created["status"] == "generated"
        assert created["summary"]["new_count"] == 1
        assert created["summary"]["resolved_count"] == 1

        get_response = client.get(f"/delta/{created['id']}")
        assert get_response.status_code == 200
        assert get_response.json()["id"] == created["id"]

        list_response = client.get(f"/scans/{target.id}/delta")
        assert list_response.status_code == 200
        comparisons = list_response.json()["comparisons"]
        assert len(comparisons) == 1
        assert comparisons[0]["id"] == created["id"]
    finally:
        db_session.close()
        Base.metadata.drop_all(bind=engine)


def test_delta_api_unknown_scan_returns_404() -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    db_session = TestingSessionLocal()
    try:
        target = _create_scan(db_session)
        client = _make_client(db_session)

        response = client.post(f"/scans/{target.id}/delta/missing")

        assert response.status_code == 404
        assert response.json()["detail"] == "Baseline scan not found"
    finally:
        db_session.close()
        Base.metadata.drop_all(bind=engine)
