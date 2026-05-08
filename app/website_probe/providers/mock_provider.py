"""Deterministic mock website probe provider.

This provider does not fetch websites. It derives lightweight test signals from
candidate fields and raw_data only.
"""

from __future__ import annotations

from urllib.parse import urlparse

from app.models.lead_candidate import LeadCandidate
from app.website_probe.providers.base import WebsiteProbeResult


class MockWebsiteProbeProvider:
    def probe(self, candidate: LeadCandidate) -> WebsiteProbeResult:
        url = _candidate_url(candidate.domain)
        normalized_domain = _normalize_domain(url)
        if not url or not normalized_domain:
            return WebsiteProbeResult(
                url=url,
                normalized_domain=normalized_domain,
                status="skipped",
                http_status=None,
                has_homepage_signal=None,
                has_impressum_signal=None,
                has_login_signal=None,
                has_shop_signal=None,
                has_booking_signal=None,
                has_checkout_signal=None,
                has_b2c_transaction_signal=None,
                evidence={
                    "mock": True,
                    "reason": "missing_domain",
                    "missing_domain": True,
                    "no_legal_conclusion": True,
                },
                confidence_score=0.2,
            )

        signals = _signals_for_candidate(candidate)
        evidence = {
            "mock": True,
            "provider": "mock_website_probe",
            "category": candidate.category,
            "candidate_source": candidate.source,
            "raw_signal_profile": (candidate.raw_data or {}).get("website_probe_profile"),
            "no_legal_conclusion": True,
        }
        return WebsiteProbeResult(
            url=url,
            normalized_domain=normalized_domain,
            status="reachable",
            http_status=200,
            has_homepage_signal=True,
            has_impressum_signal=True,
            has_login_signal=signals["login"],
            has_shop_signal=signals["shop"],
            has_booking_signal=signals["booking"],
            has_checkout_signal=signals["checkout"],
            has_b2c_transaction_signal=signals["b2c_transaction"],
            evidence=evidence,
            confidence_score=0.6,
        )


def _candidate_url(domain: str | None) -> str | None:
    if not domain:
        return None
    value = domain.strip()
    if not value:
        return None
    if value.startswith(("http://", "https://")):
        return value
    return f"https://{value}"


def _normalize_domain(url: str | None) -> str | None:
    if not url:
        return None
    parsed = urlparse(url)
    host = parsed.netloc or parsed.path
    host = host.casefold().strip().removeprefix("www.")
    return host or None


def _signals_for_candidate(candidate: LeadCandidate) -> dict[str, bool]:
    category = (candidate.category or "").casefold()
    raw_data = candidate.raw_data or {}
    profile = str(raw_data.get("website_probe_profile") or "").casefold()
    haystack = f"{category} {profile}"
    shop = "ecommerce" in haystack or "shop" in haystack or "store" in haystack
    booking = any(term in haystack for term in ("booking", "termin", "transport", "ticket"))
    login = "bank" in haystack or "banking" in haystack or "login" in haystack
    checkout = shop or "checkout" in haystack
    b2c_transaction = shop or booking or checkout
    return {
        "shop": shop,
        "booking": booking,
        "login": login,
        "checkout": checkout,
        "b2c_transaction": b2c_transaction,
    }


__all__ = ["MockWebsiteProbeProvider"]
