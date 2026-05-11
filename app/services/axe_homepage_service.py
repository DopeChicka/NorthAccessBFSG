from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from app.core.browser_config import BrowserConfig, get_browser_config
from app.models.finding import Finding, FindingCategory, FindingResponsibleRole
from app.models.scan import Scan, ScanStatus
from app.models.scan_evidence import ScanEvidence
from app.services.review_service import auto_create_review_item_for_finding

_SEVERITY_BY_AXE_IMPACT = {
    "critical": "critical",
    "serious": "high",
    "moderate": "medium",
    "minor": "low",
}
_CONFIDENCE_BY_AXE_IMPACT = {
    "critical": 0.95,
    "serious": 0.9,
    "moderate": 0.8,
    "minor": 0.65,
}


class ScanNotFoundError(Exception):
    pass


class AxeHomepageAuditError(Exception):
    pass


@dataclass(frozen=True)
class AxeViolation:
    rule_id: str
    impact: str | None
    description: str | None
    help_url: str | None
    wcag_refs: list[str]
    nodes: list[dict[str, Any]]


@dataclass(frozen=True)
class AxeHomepageResult:
    target_url: str
    final_url: str
    page_title: str | None
    http_status: int | None
    captured_at: str
    violations: list[AxeViolation]


class AxeHomepageRunner(Protocol):
    def __call__(self, url: str) -> AxeHomepageResult:
        """Open one homepage URL, run axe, and return technical findings."""


def run_axe_homepage_audit(
    db: Session,
    scan_id: str,
    *,
    runner: AxeHomepageRunner | None = None,
) -> ScanEvidence:
    scan = db.get(Scan, scan_id)
    if scan is None:
        raise ScanNotFoundError(f"Scan not found: {scan_id}")

    target_url = _target_url_for_scan(scan)
    if target_url is None:
        _mark_scan_failed(db, scan, "Scan has no URL or domain for axe homepage audit")
        raise AxeHomepageAuditError("Scan has no URL or domain for axe homepage audit")

    scan.status = ScanStatus.running
    scan.started_at = scan.started_at or datetime.now(UTC)
    db.commit()

    try:
        result = (runner or _run_playwright_axe_homepage)(target_url)
    except Exception as exc:
        _mark_scan_failed(db, scan, "Axe homepage audit failed")
        raise AxeHomepageAuditError("Axe homepage audit failed") from exc

    evidence_metadata = {
        "target_url": result.target_url,
        "final_url": result.final_url,
        "page_title": result.page_title,
        "http_status": result.http_status,
        "timestamp": result.captured_at,
        "findings_count": len(result.violations),
        "lead_id": scan.lead_id,
        "lead_candidate_id": (scan.evidence_metadata or {}).get("lead_candidate_id"),
        "no_legal_conclusion": True,
    }
    evidence = ScanEvidence(
        scan_id=scan.id,
        evidence_type="axe_homepage",
        path_or_key=f"scan-evidence/{scan.id}/axe-homepage.json",
        evidence_metadata=evidence_metadata,
        hash=None,
    )
    db.add(evidence)
    db.flush()

    for violation in result.violations:
        finding = _finding_from_violation(scan, evidence, result, violation)
        db.add(finding)
        db.flush()
        auto_create_review_item_for_finding(db, finding)

    scan.status = ScanStatus.done
    scan.completed_at = datetime.now(UTC)
    scan.evidence_metadata = {
        **(scan.evidence_metadata or {}),
        "axe_homepage": {
            "evidence_id": evidence.id,
            "path_or_key": evidence.path_or_key,
            "findings_count": len(result.violations),
            "no_legal_conclusion": True,
        },
    }
    db.commit()
    db.refresh(evidence)
    return evidence


def _finding_from_violation(
    scan: Scan,
    evidence: ScanEvidence,
    result: AxeHomepageResult,
    violation: AxeViolation,
) -> Finding:
    impact = violation.impact or "unknown"
    node_count = len(violation.nodes)
    finding_evidence = {
        "scan_evidence_id": evidence.id,
        "target_url": result.target_url,
        "final_url": result.final_url,
        "impact": impact,
        "node_count": node_count,
        "sample_targets": _sample_node_targets(violation.nodes),
        "no_legal_conclusion": True,
    }
    title = violation.description or f"Axe rule: {violation.rule_id}"
    return Finding(
        scan_id=scan.id,
        category=FindingCategory.accessibility,
        rule_id=violation.rule_id,
        severity=_SEVERITY_BY_AXE_IMPACT.get(impact, "info"),
        title=title[:255],
        description=violation.description,
        help_url=violation.help_url,
        wcag_refs=violation.wcag_refs,
        evidence=finding_evidence,
        technical_evidence=finding_evidence,
        source_tool="axe_playwright",
        recommendation="Manuelle Prüfung durchführen und technische Ursache priorisieren.",
        responsible_role=FindingResponsibleRole.developer,
        confidence_score=_confidence_for_violation(
            impact=impact,
            node_count=node_count,
        ),
        review_status="pending",
        evidence_metadata=finding_evidence,
    )


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


def _run_playwright_axe_homepage(url: str) -> AxeHomepageResult:
    try:
        from axe_playwright_python.sync_playwright import Axe
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        raise AxeHomepageAuditError("Axe or Playwright is unavailable") from exc

    config = get_browser_config()
    return _run_playwright_axe_homepage_once(url, config, Axe, sync_playwright)


def _run_playwright_axe_homepage_once(
    url: str,
    config: BrowserConfig,
    axe_cls,
    sync_playwright_fn,
) -> AxeHomepageResult:
    captured_at = datetime.now(UTC).isoformat()
    with sync_playwright_fn() as playwright:
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
            axe_response = axe_cls().run(page).response
            return AxeHomepageResult(
                target_url=url,
                final_url=page.url,
                page_title=page.title(),
                http_status=response.status if response else None,
                captured_at=captured_at,
                violations=_violations_from_axe_response(axe_response),
            )
        finally:
            browser.close()


def _violations_from_axe_response(axe_response: dict[str, Any]) -> list[AxeViolation]:
    violations = []
    for violation in axe_response.get("violations", []):
        violations.append(
            AxeViolation(
                rule_id=violation.get("id", "unknown"),
                impact=violation.get("impact"),
                description=violation.get("description") or violation.get("help"),
                help_url=violation.get("helpUrl"),
                wcag_refs=_extract_wcag_refs(violation.get("tags") or []),
                nodes=violation.get("nodes") or [],
            )
        )
    return violations


def _extract_wcag_refs(tags: list[str]) -> list[str]:
    return sorted({tag for tag in tags if tag.lower().startswith("wcag")})


def _confidence_for_violation(*, impact: str, node_count: int) -> float:
    base = _CONFIDENCE_BY_AXE_IMPACT.get(impact, 0.5)
    if node_count >= 3:
        base += 0.03
    return min(base, 0.99)


def _sample_node_targets(nodes: list[dict[str, Any]]) -> list[list[str]]:
    targets: list[list[str]] = []
    for node in nodes[:5]:
        target = node.get("target")
        if isinstance(target, list):
            targets.append([str(item) for item in target])
    return targets


def _mark_scan_failed(db: Session, scan: Scan, message: str) -> None:
    scan.status = ScanStatus.failed
    scan.failed_at = datetime.now(UTC)
    scan.error_message = message
    db.commit()


__all__ = [
    "AxeHomepageAuditError",
    "AxeHomepageResult",
    "AxeViolation",
    "ScanNotFoundError",
    "run_axe_homepage_audit",
]
