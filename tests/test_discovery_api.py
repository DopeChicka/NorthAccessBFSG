import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.discovery import router as discovery_router
from app.db.base import Base
from app.db.session import get_db
from app.models import DiscoveryRun, LeadCandidate  # noqa: F401


@pytest.fixture()
def db_session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)

    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


def make_client(db_session: Session | None = None) -> TestClient:
    app = FastAPI()
    app.include_router(discovery_router)
    if db_session is not None:
        app.dependency_overrides[get_db] = lambda: db_session
    return TestClient(app)


def test_keywords_endpoint_returns_structured_groups() -> None:
    client = make_client()

    response = client.get("/discovery/keywords")

    assert response.status_code == 200
    groups = response.json()["groups"]
    assert groups
    assert {"group_id", "label", "keywords", "bfsg_relevance_reason", "enabled"}.issubset(
        groups[0]
    )
    assert "ecommerce" in {group["group_id"] for group in groups}


def test_places_endpoint_returns_luebeck_matches() -> None:
    client = make_client()

    response = client.get("/discovery/places/Lübeck")

    assert response.status_code == 200
    payload = response.json()
    assert payload["city"] == "Lübeck"
    assert payload["matches"]
    assert {match["city"] for match in payload["matches"]} == {"Lübeck"}
    assert any(match["postal_code"] == "23552" for match in payload["matches"])


def test_places_endpoint_accepts_luebeck_transliteration() -> None:
    client = make_client()

    response = client.get("/discovery/places/Luebeck")

    assert response.status_code == 200
    assert {match["city"] for match in response.json()["matches"]} == {"Lübeck"}


def test_create_discovery_run_endpoint_returns_done_and_query_count(db_session: Session) -> None:
    client = make_client(db_session)

    response = client.post("/discovery/runs/Lübeck")

    assert response.status_code == 200
    payload = response.json()
    assert payload["discovery_run_id"]
    assert payload["city"] == "Lübeck"
    assert payload["status"] == "done"
    assert payload["postal_codes_count"] > 0
    assert payload["query_count"] > 0


def test_get_discovery_run_endpoint_returns_stored_query_plan(db_session: Session) -> None:
    client = make_client(db_session)
    create_response = client.post("/discovery/runs/Lübeck")
    run_id = create_response.json()["discovery_run_id"]

    response = client.get(f"/discovery/runs/{run_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == run_id
    assert payload["status"] == "done"
    assert payload["postal_codes"]
    assert payload["keyword_groups"]
    assert payload["query_plan"]
    assert payload["error_message"] is None


def test_discovery_run_candidates_endpoint_returns_empty_list(db_session: Session) -> None:
    client = make_client(db_session)
    create_response = client.post("/discovery/runs/Lübeck")
    run_id = create_response.json()["discovery_run_id"]

    response = client.get(f"/discovery/runs/{run_id}/candidates")

    assert response.status_code == 200
    assert response.json() == {"discovery_run_id": run_id, "candidates": []}


def test_create_discovery_run_unknown_city_returns_clear_error(db_session: Session) -> None:
    client = make_client(db_session)

    response = client.post("/discovery/runs/Atlantis")

    assert response.status_code == 404
    assert "No places found for city: Atlantis" in response.json()["detail"]
