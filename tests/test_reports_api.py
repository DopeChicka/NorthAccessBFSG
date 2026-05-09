from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.reports import router as reports_router
from app.db.base import Base
from app.db.session import get_db
from app.models import Lead, Report, Scan, ScanStatus  # noqa: F401


def _make_client(db_session: Session) -> TestClient:
    app = FastAPI()
    app.include_router(reports_router)
    app.dependency_overrides[get_db] = lambda: db_session
    return TestClient(app)


def test_report_api_create_get_and_list() -> None:
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
        scan = Scan(lead_id=lead.id, status=ScanStatus.done)
        db_session.add(scan)
        db_session.commit()
        db_session.refresh(scan)
        client = _make_client(db_session)

        create_response = client.post(f"/scans/{scan.id}/reports/json")
        assert create_response.status_code == 200
        created = create_response.json()
        assert created["scan_id"] == scan.id
        assert created["status"] == "generated"
        assert created["report_type"] == "json"
        assert created["summary"]["finding_count"] == 0
        assert created["evidence_manifest"]["evidence_count"] == 0

        get_response = client.get(f"/reports/{created['id']}")
        assert get_response.status_code == 200
        assert get_response.json()["id"] == created["id"]

        list_response = client.get(f"/scans/{scan.id}/reports")
        assert list_response.status_code == 200
        reports = list_response.json()["reports"]
        assert len(reports) == 1
        assert reports[0]["id"] == created["id"]
    finally:
        db_session.close()
        Base.metadata.drop_all(bind=engine)


def test_report_api_unknown_scan_returns_404() -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    db_session = TestingSessionLocal()
    try:
        client = _make_client(db_session)

        response = client.post("/scans/missing/reports/json")

        assert response.status_code == 404
        assert response.json()["detail"] == "Scan not found"
    finally:
        db_session.close()
        Base.metadata.drop_all(bind=engine)
