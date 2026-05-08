import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.discovery import router as discovery_router
from app.db.base import Base
from app.db.session import get_db
from app.models import CompanyEnrichment, CompanyQualification, DiscoveryRun, LeadCandidate  # noqa: F401


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


def test_mock_provider_endpoint_persists_candidates(db_session: Session) -> None:
    client = make_client(db_session)
    create_response = client.post("/discovery/runs/Lübeck")
    run_id = create_response.json()["discovery_run_id"]

    provider_response = client.post(f"/discovery/runs/{run_id}/providers/mock")
    candidates_response = client.get(f"/discovery/runs/{run_id}/candidates")

    assert provider_response.status_code == 200
    assert provider_response.json() == {
        "discovery_run_id": run_id,
        "provider": "mock",
        "candidates_created": 10,
        "candidates_total": 10,
    }
    candidates = candidates_response.json()["candidates"]
    assert len(candidates) == 10
    assert candidates[0]["source"] == "mock"
    assert candidates[0]["company_name"].startswith("Mock Candidate Lübeck")
    assert candidates[0]["raw_data"]["mock"] is True


def test_google_places_endpoint_disabled_returns_clear_error(db_session: Session) -> None:
    client = make_client(db_session)
    create_response = client.post("/discovery/runs/Lübeck")
    run_id = create_response.json()["discovery_run_id"]

    response = client.post(f"/discovery/runs/{run_id}/providers/google-places")

    assert response.status_code == 503
    assert response.json()["detail"] == "Google Places API provider is disabled"


def test_candidate_enrichment_mock_endpoint_persists_and_reads_latest(
    db_session: Session,
) -> None:
    client = make_client(db_session)
    create_response = client.post("/discovery/runs/Lübeck")
    run_id = create_response.json()["discovery_run_id"]
    client.post(f"/discovery/runs/{run_id}/providers/mock")
    candidate_id = client.get(f"/discovery/runs/{run_id}/candidates").json()["candidates"][0]["id"]

    enrichment_response = client.post(
        f"/discovery/candidates/{candidate_id}/enrichment/mock"
    )
    read_response = client.get(f"/discovery/candidates/{candidate_id}/enrichment")

    assert enrichment_response.status_code == 200
    enrichment_summary = enrichment_response.json()
    assert enrichment_summary["candidate_id"] == candidate_id
    assert enrichment_summary["source"] == "mock_company_data"
    assert enrichment_summary["confidence_score"] == 0.2

    assert read_response.status_code == 200
    enrichment = read_response.json()
    assert enrichment["id"] == enrichment_summary["enrichment_id"]
    assert enrichment["candidate_id"] == candidate_id
    assert enrichment["raw_data"]["mock"] is True
    assert enrichment["raw_data"]["profile"] == "missing"


def test_candidate_enrichment_unknown_candidate_returns_clear_error(db_session: Session) -> None:
    client = make_client(db_session)

    response = client.post("/discovery/candidates/missing/enrichment/mock")

    assert response.status_code == 404
    assert "Lead candidate not found: missing" in response.json()["detail"]


def test_candidate_qualification_precheck_for_mock_candidate(db_session: Session) -> None:
    client = make_client(db_session)
    create_response = client.post("/discovery/runs/Lübeck")
    run_id = create_response.json()["discovery_run_id"]
    client.post(f"/discovery/runs/{run_id}/providers/mock")
    candidates = client.get(f"/discovery/runs/{run_id}/candidates").json()["candidates"]
    candidate_id = candidates[0]["id"]

    precheck_response = client.post(
        f"/discovery/candidates/{candidate_id}/qualification/precheck"
    )
    read_response = client.get(f"/discovery/candidates/{candidate_id}/qualification")

    assert precheck_response.status_code == 200
    precheck = precheck_response.json()
    assert precheck["candidate_id"] == candidate_id
    assert precheck["status"] == "needs_human_review"
    assert precheck["is_microenterprise"] is None
    assert precheck["confidence_score"] == 0.1

    assert read_response.status_code == 200
    qualification = read_response.json()
    assert qualification["candidate_id"] == candidate_id
    assert qualification["status"] == "needs_human_review"
    assert qualification["evidence"]["is_mock_or_test_data"] is True
    assert qualification["evidence"]["requires_company_enrichment"] is True


def test_qualification_unknown_candidate_returns_clear_error(db_session: Session) -> None:
    client = make_client(db_session)

    response = client.post("/discovery/candidates/missing/qualification/precheck")

    assert response.status_code == 404
    assert "Lead candidate not found: missing" in response.json()["detail"]


def test_mock_provider_endpoint_unknown_run_returns_clear_error(db_session: Session) -> None:
    client = make_client(db_session)

    response = client.post("/discovery/runs/missing/providers/mock")

    assert response.status_code == 404
    assert "Discovery run not found: missing" in response.json()["detail"]


def test_create_discovery_run_unknown_city_returns_clear_error(db_session: Session) -> None:
    client = make_client(db_session)

    response = client.post("/discovery/runs/Atlantis")

    assert response.status_code == 404
    assert "No places found for city: Atlantis" in response.json()["detail"]
