from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

from axe_playwright_python.sync_playwright import Axe
from playwright.sync_api import sync_playwright

from app.core.browser_config import BrowserConfig, get_browser_config
from app.evidence.storage import EvidenceArtifact

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


@dataclass(frozen=True)
class EngineFinding:
    rule_id: str
    severity: str
    wcag_refs: list[str]
    confidence_score: float
    description: str | None
    help_url: str | None
    evidence_metadata: dict[str, Any]


@dataclass(frozen=True)
class PlaywrightScanResult:
    target_url: str
    current_url: str
    captured_at: str
    evidence_metadata: dict[str, Any]
    evidence_artifacts: list[EvidenceArtifact]
    findings: list[EngineFinding]


def run_accessibility_scan(domain: str) -> PlaywrightScanResult:
    config = get_browser_config()
    target_url = normalize_target_url(domain)
    last_error: Exception | None = None

    for attempt in range(config.retries + 1):
        try:
            return _run_once(target_url=target_url, config=config, attempt=attempt)
        except Exception as exc:
            last_error = exc
            if attempt < config.retries:
                time.sleep(min(2**attempt, 5))

    raise RuntimeError(f"Playwright scan failed for {target_url}") from last_error


def normalize_target_url(domain: str) -> str:
    candidate = domain.strip()
    parsed = urlparse(candidate)
    if parsed.scheme:
        return candidate
    return f"https://{candidate}"


def _run_once(
    target_url: str, config: BrowserConfig, attempt: int
) -> PlaywrightScanResult:
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
            page.goto(
                target_url,
                wait_until=config.wait_until,
                timeout=config.navigation_timeout_ms,
            )

            axe_response = Axe().run(page).response
            dom_snapshot = page.content()
            screenshot_bytes = page.screenshot(full_page=True)
            accessibility_tree = _capture_accessibility_tree(page)
            accessibility_tree_json = _json_dump(accessibility_tree)
            current_url = page.url
            evidence_artifacts = [
                EvidenceArtifact(
                    type="screenshot",
                    content=screenshot_bytes,
                    content_type="image/png",
                    extension="png",
                ),
                EvidenceArtifact(
                    type="dom",
                    content=dom_snapshot.encode("utf-8"),
                    content_type="text/html; charset=utf-8",
                    extension="html",
                ),
                EvidenceArtifact(
                    type="a11y_tree",
                    content=accessibility_tree_json.encode("utf-8"),
                    content_type="application/json",
                    extension="json",
                ),
            ]
            evidence_metadata = _build_scan_evidence_metadata(
                accessibility_tree=accessibility_tree,
                accessibility_tree_json=accessibility_tree_json,
                axe_response=axe_response,
                captured_at=captured_at,
                config=config,
                current_url=current_url,
                dom_snapshot=dom_snapshot,
                screenshot_bytes=screenshot_bytes,
                target_url=target_url,
                attempt=attempt,
            )
            findings = _findings_from_axe_response(axe_response, evidence_metadata)

            return PlaywrightScanResult(
                target_url=target_url,
                current_url=current_url,
                captured_at=captured_at,
                evidence_metadata=evidence_metadata,
                evidence_artifacts=evidence_artifacts,
                findings=findings,
            )
        finally:
            browser.close()


def _capture_accessibility_tree(page) -> dict[str, Any] | None:
    try:
        return page.accessibility.snapshot(interesting_only=False)
    except Exception:
        return None


def _build_scan_evidence_metadata(
    *,
    accessibility_tree: dict[str, Any] | None,
    accessibility_tree_json: str,
    axe_response: dict[str, Any],
    captured_at: str,
    config: BrowserConfig,
    current_url: str,
    dom_snapshot: str,
    screenshot_bytes: bytes,
    target_url: str,
    attempt: int,
) -> dict[str, Any]:
    return {
        "target_url": target_url,
        "current_url": current_url,
        "captured_at": captured_at,
        "browser": {
            "name": config.browser_name,
            "headless": config.headless,
            "viewport": {
                "width": config.viewport_width,
                "height": config.viewport_height,
            },
            "navigation_timeout_ms": config.navigation_timeout_ms,
            "attempt": attempt + 1,
        },
        "axe": {
            "violations_count": len(axe_response.get("violations", [])),
            "passes_count": len(axe_response.get("passes", [])),
            "incomplete_count": len(axe_response.get("incomplete", [])),
            "inapplicable_count": len(axe_response.get("inapplicable", [])),
        },
        "screenshot": {
            "storage": "pending",
            "full_page": True,
            "byte_count": len(screenshot_bytes),
            "sha256": hashlib.sha256(screenshot_bytes).hexdigest(),
        },
        "dom_snapshot": {
            "storage": "pending",
            "char_count": len(dom_snapshot),
            "sha256": _sha256_text(dom_snapshot),
        },
        "accessibility_tree": {
            "storage": "pending",
            "available": accessibility_tree is not None,
            "node_count": _count_accessibility_nodes(accessibility_tree),
            "sha256": _sha256_text(accessibility_tree_json),
        },
    }


def _findings_from_axe_response(
    axe_response: dict[str, Any], scan_evidence: dict[str, Any]
) -> list[EngineFinding]:
    findings: list[EngineFinding] = []
    for violation in axe_response.get("violations", []):
        impact = violation.get("impact") or "unknown"
        nodes = violation.get("nodes") or []
        wcag_refs = _extract_wcag_refs(violation.get("tags") or [])
        confidence_score = _confidence_for_violation(impact=impact, node_count=len(nodes))

        findings.append(
            EngineFinding(
                rule_id=violation.get("id", "unknown"),
                severity=_SEVERITY_BY_AXE_IMPACT.get(impact, "info"),
                wcag_refs=wcag_refs,
                confidence_score=confidence_score,
                description=violation.get("description") or violation.get("help"),
                help_url=violation.get("helpUrl"),
                evidence_metadata={
                    **scan_evidence,
                    "axe_violation": {
                        "impact": impact,
                        "help": violation.get("help"),
                        "help_url": violation.get("helpUrl"),
                        "node_count": len(nodes),
                        "sample_targets": _sample_node_targets(nodes),
                    },
                },
            )
        )

    return findings


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


def _count_accessibility_nodes(node: dict[str, Any] | None) -> int:
    if not node:
        return 0
    children = node.get("children") or []
    return 1 + sum(_count_accessibility_nodes(child) for child in children)


def _json_dump(value: Any) -> str:
    return json.dumps(value, default=str, ensure_ascii=False, sort_keys=True)


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
