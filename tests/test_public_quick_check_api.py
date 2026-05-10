from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import public as public_api
from app.api.public import router as public_router
from app.core.config import settings
from app.main import configure_cors
from app.services.public_quick_check_service import (
    DISCLAIMER_TEXT,
    QuickCheckValidationError,
)


def _make_client() -> TestClient:
    app = FastAPI()
    configure_cors(app, settings.frontend_origins)
    app.include_router(public_router)
    return TestClient(app)


def test_public_quick_check_endpoint_response_shape(monkeypatch) -> None:
    def fake_run_public_quick_check(**kwargs) -> dict[str, object]:
        return {
            "status": "completed",
            "inputUrl": "example.com",
            "normalizedUrl": "https://example.com",
            "scannedAt": "2026-05-10T10:00:00+00:00",
            "summary": {
                "critical": 0,
                "serious": 0,
                "moderate": 0,
                "minor": 0,
                "info": 0,
            },
            "score": {
                "accessibility": 100,
                "technical": 100,
                "privacy": 100,
                "seo": 100,
            },
            "checks": {
                "accessibility": {
                    "label": "Barrierefreiheit",
                    "status": "checked",
                    "findingsCount": 0,
                },
                "technical": {
                    "label": "Technik",
                    "https": True,
                    "reachable": True,
                    "finalUrl": "https://example.com",
                },
                "privacy": {
                    "label": "Datenschutz-Hinweise",
                    "impressumLink": True,
                    "privacyLink": True,
                    "detectedTrackers": [],
                },
                "seo": {
                    "label": "SEO-Grundlagen",
                    "title": True,
                    "metaDescription": True,
                    "h1": True,
                    "htmlLang": True,
                },
            },
            "findings": [],
            "disclaimer": DISCLAIMER_TEXT,
        }

    monkeypatch.setattr(public_api, "run_public_quick_check", fake_run_public_quick_check)
    client = _make_client()

    response = client.post("/public/quick-check", json={"domain": "example.com"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "completed"
    assert isinstance(payload["summary"], dict)
    assert isinstance(payload["score"], dict)
    assert isinstance(payload["checks"], dict)
    assert payload["disclaimer"] == DISCLAIMER_TEXT


def test_public_quick_check_endpoint_returns_400_for_validation_error(
    monkeypatch,
) -> None:
    def failing_run_public_quick_check(**kwargs) -> dict[str, object]:
        raise QuickCheckValidationError("Invalid URL or domain")

    monkeypatch.setattr(
        public_api,
        "run_public_quick_check",
        failing_run_public_quick_check,
    )
    client = _make_client()

    response = client.post("/public/quick-check", json={"url": "ftp://example.com"})

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid URL or domain"


def test_public_quick_check_endpoint_requires_input() -> None:
    client = _make_client()

    response = client.post("/public/quick-check", json={})

    assert response.status_code == 422


def test_public_quick_check_preflight_options_is_allowed() -> None:
    client = _make_client()

    response = client.options(
        "/public/quick-check",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.status_code != 405
    assert response.status_code in {200, 204}
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"
