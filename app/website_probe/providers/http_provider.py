"""Live HTTP website probe provider.

This provider performs one lightweight HTTP GET when explicitly enabled. It
does not crawl, submit forms, run Playwright, or produce legal conclusions.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable
from urllib.parse import urlparse

import httpx

from app.core.config import Settings, settings
from app.models.lead_candidate import LeadCandidate
from app.website_probe.providers.base import WebsiteProbeResult


class LiveWebsiteProbeDisabledError(RuntimeError):
    """Raised when the live HTTP website probe is disabled by configuration."""


@dataclass(frozen=True)
class HttpFetchResult:
    url: str
    status_code: int
    body: bytes


HttpFetcher = Callable[[str, Settings], HttpFetchResult]


class HttpWebsiteProbeProvider:
    def __init__(
        self,
        *,
        settings_: Settings = settings,
        fetcher: HttpFetcher | None = None,
    ) -> None:
        self.settings = settings_
        self.fetcher = fetcher or _fetch_url

    def probe(self, candidate: LeadCandidate) -> WebsiteProbeResult:
        if not self.settings.website_probe_live_enabled:
            raise LiveWebsiteProbeDisabledError("Live website probe is disabled")

        url = _candidate_url(candidate)
        normalized_domain = _normalize_domain(url)
        if not url or not normalized_domain:
            return _missing_domain_result()

        try:
            response = self.fetcher(url, self.settings)
        except httpx.TimeoutException as exc:
            return _unreachable_result(url, normalized_domain, "timeout", str(exc))
        except httpx.HTTPError as exc:
            return _unreachable_result(url, normalized_domain, "http_error", str(exc))

        signals = _extract_signals(response.body)
        status = _status_for_http_status(response.status_code)
        final_normalized_domain = _normalize_domain(response.url) or normalized_domain
        return WebsiteProbeResult(
            url=response.url,
            normalized_domain=final_normalized_domain,
            status=status,
            http_status=response.status_code,
            has_homepage_signal=status == "reachable",
            has_impressum_signal=bool(signals["impressum"]),
            has_login_signal=bool(signals["login"]),
            has_shop_signal=bool(signals["shop"]),
            has_booking_signal=bool(signals["booking"]),
            has_checkout_signal=bool(signals["checkout"]),
            has_b2c_transaction_signal=bool(
                signals["shop"] or signals["booking"] or signals["checkout"]
            ),
            evidence={
                "provider": "live_http_website_probe",
                "checked_url": response.url,
                "http_status": response.status_code,
                "matched_keywords": signals,
                "no_legal_conclusion": True,
            },
            confidence_score=0.7 if status == "reachable" else 0.3,
        )


def _fetch_url(url: str, settings_: Settings) -> HttpFetchResult:
    headers = {"User-Agent": settings_.website_probe_user_agent}
    with httpx.Client(
        timeout=settings_.website_probe_timeout_seconds,
        follow_redirects=True,
        headers=headers,
    ) as client:
        with client.stream("GET", url) as response:
            body = bytearray()
            for chunk in response.iter_bytes():
                remaining = settings_.website_probe_max_body_bytes - len(body)
                if remaining <= 0:
                    break
                body.extend(chunk[:remaining])
            return HttpFetchResult(
                url=str(response.url),
                status_code=response.status_code,
                body=bytes(body),
            )


def _candidate_url(candidate: LeadCandidate) -> str | None:
    raw_data = candidate.raw_data or {}
    value = candidate.domain or raw_data.get("website") or raw_data.get("domain")
    value = value or raw_data.get("website_url") or raw_data.get("url")
    if not value:
        return None

    value = str(value).strip()
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


def _missing_domain_result() -> WebsiteProbeResult:
    return WebsiteProbeResult(
        url=None,
        normalized_domain=None,
        status="skipped",
        evidence={
            "provider": "live_http_website_probe",
            "reason": "missing_domain",
            "missing_domain": True,
            "no_legal_conclusion": True,
        },
        confidence_score=0.2,
    )


def _unreachable_result(
    url: str,
    normalized_domain: str,
    reason: str,
    error_message: str,
) -> WebsiteProbeResult:
    return WebsiteProbeResult(
        url=url,
        normalized_domain=normalized_domain,
        status="unreachable",
        evidence={
            "provider": "live_http_website_probe",
            "checked_url": url,
            "reason": reason,
            "error_message": error_message,
            "matched_keywords": {},
            "no_legal_conclusion": True,
        },
        confidence_score=0.2,
    )


def _status_for_http_status(http_status: int) -> str:
    if 200 <= http_status < 400:
        return "reachable"
    if 400 <= http_status < 500:
        return "needs_review"
    return "unreachable"


def _extract_signals(body: bytes) -> dict[str, list[str]]:
    raw_text = body.decode("utf-8", errors="ignore").casefold()
    visible_text = re.sub(r"<[^>]+>", " ", raw_text)
    text = f"{raw_text} {visible_text}"
    return {
        "impressum": _matched_keywords(text, ("impressum", "legal notice")),
        "login": _matched_keywords(text, ("login", "log in", "signin", "sign in")),
        "shop": _matched_keywords(text, ("shop", "store", "warenkorb")),
        "booking": _matched_keywords(text, ("booking", "book now", "termin", "ticket")),
        "checkout": _matched_keywords(text, ("checkout", "cart", "basket", "kasse")),
    }


def _matched_keywords(text: str, keywords: tuple[str, ...]) -> list[str]:
    return [keyword for keyword in keywords if keyword in text]


__all__ = [
    "HttpFetchResult",
    "HttpWebsiteProbeProvider",
    "LiveWebsiteProbeDisabledError",
]
