from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.discovery import router as discovery_router


def make_client() -> TestClient:
    app = FastAPI()
    app.include_router(discovery_router)
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
