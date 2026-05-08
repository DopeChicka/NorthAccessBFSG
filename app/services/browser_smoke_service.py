from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright
from sqlalchemy.orm import Session

from app.core.browser_config import BrowserConfig, get_browser_config
from app.models.scan import Scan, ScanStatus
from app.models.scan_evidence import ScanEvidence


class ScanNotFoundError(Exception):
    pass


class BrowserSmokeProbeError(Exception):
    pass


@dataclass(frozen=True)
class BrowserSmokeResult:
    target_url: str
    final_url: str
    page_title: str | None
    http_status: int | None
    captured_at: str


class BrowserSmokeRunner(Protocol):
    def __call__(self, url: str) -> BrowserSmokeResult:
        """Open one URL and return lightweight browser metadata."""


def run_browser_smoke_probe(
    db: Session,
    scan_id: str,
    *,
    runner: BrowserSmokeRunner | None = None,
) -> ScanEvidence:
    scan = db.get(Scan, scan_id)
    if scan is None:
        raise ScanNotFoundError(f"Scan not found: {scan_id}")

    target_url = _target_url_for_scan(scan)
    if target_url is None:
        _mark_scan_failed(db, scan, "Scan has no URL or domain for browser smoke probe")
        raise BrowserSmokeProbeError("Scan has no URL or domain for browser smoke probe")

    scan.status = ScanStatus.running
    scan.started_at = scan.started_at or datetime.now(UTC)
    db.commit()

    try:
        result = (runner or _run_playwright_smoke)(target_url)
    except Exception as exc:
        _mark_scan_failed(db, scan, "Browser smoke probe failed")
        raise BrowserSmokeProbeError("Browser smoke probe failed") from exc

    metadata = {
        "target_url": result.target_url,
        "final_url": result.final_url,
        "page_title": result.page_title,
        "http_status": result.http_status,
        "timestamp": result.captured_at,
        "lead_id": scan.lead_id,
        "lead_candidate_id": (scan.evidence_metadata or {}).get("lead_candidate_id"),
        "no_legal_conclusion": True,
    }
    evidence = ScanEvidence(
        scan_id=scan.id,
        evidence_type="browser_smoke",
        path_or_key=f"scan-evidence/{scan.id}/browser-smoke.json",
        evidence_metadata=metadata,
        hash=None,
    )
    db.add(evidence)
    db.flush()
    scan.status = ScanStatus.done
    scan.completed_at = datetime.now(UTC)
    scan.evidence_metadata = {
        **(scan.evidence_metadata or {}),
        "browser_smoke": {
            "evidence_id": evidence.id,
            "path_or_key": evidence.path_or_key,
            "no_legal_conclusion": True,
        },
    }
    db.commit()
    db.refresh(evidence)
    return evidence


def _target_url_for_scan(scan: Scan) -> str | None:
    domain = scan.lead.domain if scan.lead else None
    if not domain:
        return None

    value = domain.strip()
    if not value:
        return None

    parsed = urlparse(value)
    if parsed.scheme:
        return value
    return f"https://{value}"


def _run_playwright_smoke(url: str) -> BrowserSmokeResult:
    config = get_browser_config()
    return _run_playwright_smoke_once(url, config)


def _run_playwright_smoke_once(url: str, config: BrowserConfig) -> BrowserSmokeResult:
    captured_at = datetime.now(UTC).isoformat()
    with sync_playwright() as playwright:
        browser_type = getattr(playwright, config.browser_name)
        launch_args = ["--no-sandbox"] if config.browser_name == "chromium" else []
        browser = browser_type.launch(headless=config.headless, args=launch_args)
        try:
            context = browser.new_context(
                viewport={
                    "width": config.viewport_width,
                    "height": config.viewport_height,
                }
            )
            context.set_default_timeout(config.action_timeout_ms)
            context.set_default_navigation_timeout(config.navigation_timeout_ms)
            page = context.new_page()
            response = page.goto(
                url,
                wait_until=config.wait_until,
                timeout=config.navigation_timeout_ms,
            )
            return BrowserSmokeResult(
                target_url=url,
                final_url=page.url,
                page_title=page.title(),
                http_status=response.status if response else None,
                captured_at=captured_at,
            )
        finally:
            browser.close()


def _mark_scan_failed(db: Session, scan: Scan, message: str) -> None:
    scan.status = ScanStatus.failed
    scan.failed_at = datetime.now(UTC)
    scan.error_message = message
    db.commit()


__all__ = [
    "BrowserSmokeProbeError",
    "BrowserSmokeResult",
    "ScanNotFoundError",
    "run_browser_smoke_probe",
]
