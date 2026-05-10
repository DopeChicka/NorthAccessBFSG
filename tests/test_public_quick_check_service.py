from __future__ import annotations

import pytest

from app.services.public_quick_check_service import (
    DISCLAIMER_TEXT,
    QuickCheckFetchResult,
    QuickCheckValidationError,
    run_public_quick_check,
)


def test_public_quick_check_response_schema_and_findings() -> None:
    html = """
    <html lang="de">
      <head>
        <title>Example</title>
        <script src="https://www.googletagmanager.com/gtm.js"></script>
      </head>
      <body>
        <a href="/impressum">Impressum</a>
      </body>
    </html>
    """

    def fake_fetcher(url: str, **kwargs) -> QuickCheckFetchResult:
        assert url == "https://example.com"
        return QuickCheckFetchResult(
            status_code=200,
            final_url="https://www.example.com/",
            html=html,
        )

    response = run_public_quick_check(
        url=None,
        domain="example.com",
        timeout_seconds=5,
        user_agent="test-agent",
        max_body_bytes=200000,
        fetcher=fake_fetcher,
    )

    assert response["status"] == "completed"
    assert isinstance(response["summary"], dict)
    assert set(response["summary"].keys()) == {
        "critical",
        "serious",
        "moderate",
        "minor",
        "info",
    }
    assert isinstance(response["score"], dict)
    assert set(response["score"].keys()) == {
        "accessibility",
        "technical",
        "privacy",
        "seo",
    }
    assert isinstance(response["checks"], dict)
    assert set(response["checks"].keys()) == {
        "accessibility",
        "technical",
        "privacy",
        "seo",
    }
    assert response["checks"]["technical"]["finalUrl"] == "https://www.example.com/"
    assert response["checks"]["privacy"]["impressumLink"] is True
    assert response["checks"]["privacy"]["privacyLink"] is False
    assert response["checks"]["seo"]["metaDescription"] is False
    assert response["disclaimer"] == DISCLAIMER_TEXT

    assert len(response["findings"]) > 0
    first = response["findings"][0]
    assert "id" in first
    assert "category" in first
    assert "severity" in first
    assert "title" in first
    assert "description" in first
    assert "evidence" in first
    assert "recommendation" in first
    assert "legalDisclaimer" in first


def test_public_quick_check_unreachable_maps_to_critical_technical() -> None:
    def failing_fetcher(url: str, **kwargs) -> QuickCheckFetchResult:
        raise RuntimeError("network unavailable")

    response = run_public_quick_check(
        url="example.com",
        domain=None,
        timeout_seconds=5,
        user_agent="test-agent",
        max_body_bytes=200000,
        fetcher=failing_fetcher,
    )

    assert response["status"] == "completed"
    assert response["checks"]["technical"]["reachable"] is False
    assert any(
        finding["id"] == "website_unreachable"
        and finding["category"] == "technical"
        and finding["severity"] == "critical"
        for finding in response["findings"]
    )


def test_public_quick_check_requires_url_or_domain() -> None:
    with pytest.raises(QuickCheckValidationError, match="Either url or domain"):
        run_public_quick_check(
            url="",
            domain="",
            timeout_seconds=5,
            user_agent="test-agent",
            max_body_bytes=200000,
        )
