from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.journeys import router as journeys_router
from app.db.base import Base
from app.db.session import get_db
from app.models import Lead, Scan, ScanStatus  # noqa: F401


def _make_client(db_session: Session) -> TestClient:
    app = FastAPI()
    app.include_router(journeys_router)
    app.dependency_overrides[get_db] = lambda: db_session
    return TestClient(app)


def test_list_journeys_endpoint_works() -> None:
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
        db_session.commit()
        db_session.refresh(scan)
        client = _make_client(db_session)

        plan_response = client.post(f"/scans/{scan.id}/journeys/plan")
        assert plan_response.status_code == 200
        assert plan_response.json()["journeys"][0]["journey_type"] == "homepage"

        list_response = client.get(f"/scans/{scan.id}/journeys")
        assert list_response.status_code == 200
        journeys = list_response.json()["journeys"]
        assert len(journeys) == 3
        assert journeys[0]["scan_id"] == scan.id
    finally:
        db_session.close()
        Base.metadata.drop_all(bind=engine)
