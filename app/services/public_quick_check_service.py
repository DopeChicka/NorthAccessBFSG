from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from html.parser import HTMLParser
from typing import Protocol
from urllib.parse import urlparse, urlunparse

import httpx

TRACKER_DOMAINS = (
    "google-analytics.com",
    "googletagmanager.com",
    "facebook.net",
    "doubleclick.net",
)

DISCLAIMER_TEXT = (
    "Diese automatisierte Vorprüfung liefert technische Hinweise und ersetzt keine "
    "vollständige manuelle Barrierefreiheitsprüfung, keine Rechtsberatung und keine "
    "behördliche Zertifizierung."
)
FINDING_LEGAL_DISCLAIMER = "Technischer Hinweis, keine Rechtsberatung."


class QuickCheckValidationError(ValueError):
    pass


@dataclass(frozen=True)
class QuickCheckFetchResult:
    status_code: int
    final_url: str
    html: str


class QuickCheckFetcher(Protocol):
    def __call__(
        self,
        url: str,
        *,
        timeout_seconds: int,
        user_agent: str,
        max_body_bytes: int,
    ) -> QuickCheckFetchResult:
        """Fetch one page and return lightweight HTTP and HTML data."""


def run_public_quick_check(
    *,
    url: str | None,
    domain: str | None,
    timeout_seconds: int,
    user_agent: str,
    max_body_bytes: int,
    fetcher: QuickCheckFetcher | None = None,
) -> dict[str, object]:
    input_value = _pick_input(url=url, domain=domain)
    normalized_url = normalize_quick_check_url(input_value)
    scanned_at = datetime.now(UTC).isoformat()
    final_url = normalized_url
    reachable = False
    title_ok = False
    meta_description_ok = False
    h1_ok = False
    html_lang_ok = False
    impressum_ok = False
    privacy_ok = False
    detected_trackers: list[str] = []

    try:
        fetch_result = (fetcher or _fetch_once)(
            normalized_url,
            timeout_seconds=timeout_seconds,
            user_agent=user_agent,
            max_body_bytes=max_body_bytes,
        )
    except Exception:
        pass
    else:
        final_url = fetch_result.final_url or normalized_url
        reachable = fetch_result.status_code < 500
        parser = _QuickCheckHtmlParser()
        parser.feed(fetch_result.html)
        parser.close()

        title_ok = bool(parser.title)
        meta_description_ok = bool(parser.meta_description)
        h1_ok = bool(parser.h1_text)
        html_lang_ok = bool(parser.html_lang)
        impressum_ok = _link_keyword_detected(parser.links, ("impressum",))
        privacy_ok = _link_keyword_detected(
            parser.links,
            ("datenschutz", "datenschutzerklaerung", "privacy", "privacy-policy"),
        )
        detected_trackers = _detect_trackers(fetch_result.html)

    https_ok = final_url.lower().startswith("https://")
    findings = _build_findings(
        normalized_url=normalized_url,
        final_url=final_url,
        reachable=reachable,
        https_ok=https_ok,
        title_ok=title_ok,
        meta_description_ok=meta_description_ok,
        h1_ok=h1_ok,
        html_lang_ok=html_lang_ok,
        impressum_ok=impressum_ok,
        privacy_ok=privacy_ok,
        detected_trackers=detected_trackers,
    )
    summary = _build_summary(findings)
    checks = _build_checks(
        final_url=final_url,
        reachable=reachable,
        https_ok=https_ok,
        title_ok=title_ok,
        meta_description_ok=meta_description_ok,
        h1_ok=h1_ok,
        html_lang_ok=html_lang_ok,
        impressum_ok=impressum_ok,
        privacy_ok=privacy_ok,
        detected_trackers=detected_trackers,
        findings=findings,
    )
    score = _build_score(findings)
    return {
        "status": "completed",
        "inputUrl": input_value,
        "normalizedUrl": normalized_url,
        "scannedAt": scanned_at,
        "summary": summary,
        "score": score,
        "checks": checks,
        "findings": findings,
        "disclaimer": DISCLAIMER_TEXT,
    }


def normalize_quick_check_url(value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise QuickCheckValidationError("Either url or domain must be provided")

    candidate = cleaned if "://" in cleaned else f"https://{cleaned}"
    parsed = urlparse(candidate)
    if parsed.scheme.lower() not in {"http", "https"}:
        raise QuickCheckValidationError("Only http and https URLs are supported")
    if not parsed.netloc:
        raise QuickCheckValidationError("Invalid URL or domain")

    normalized = parsed._replace(fragment="")
    return urlunparse(normalized)


def _pick_input(*, url: str | None, domain: str | None) -> str:
    if url and url.strip():
        return url.strip()
    if domain and domain.strip():
        return domain.strip()
    raise QuickCheckValidationError("Either url or domain must be provided")


def _fetch_once(
    url: str,
    *,
    timeout_seconds: int,
    user_agent: str,
    max_body_bytes: int,
) -> QuickCheckFetchResult:
    with httpx.Client(
        follow_redirects=True,
        timeout=timeout_seconds,
        headers={"User-Agent": user_agent},
    ) as client:
        response = client.get(url)
    body = response.content[:max_body_bytes]
    encoding = response.encoding or "utf-8"
    html = body.decode(encoding, errors="ignore")
    return QuickCheckFetchResult(
        status_code=response.status_code,
        final_url=str(response.url),
        html=html,
    )


def _build_findings(
    *,
    normalized_url: str,
    final_url: str,
    reachable: bool,
    https_ok: bool,
    title_ok: bool,
    meta_description_ok: bool,
    h1_ok: bool,
    html_lang_ok: bool,
    impressum_ok: bool,
    privacy_ok: bool,
    detected_trackers: list[str],
) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    evidence_url = final_url or normalized_url

    if not reachable:
        findings.append(
            _finding(
                finding_id="website_unreachable",
                category="technical",
                severity="critical",
                title="Website nicht erreichbar",
                description="Die Website war fuer den Quick-Check nicht erreichbar.",
                recommendation="Erreichbarkeit pruefen und erneut testen.",
                evidence_url=evidence_url,
            )
        )
    if not https_ok:
        findings.append(
            _finding(
                finding_id="https_missing",
                category="technical",
                severity="serious",
                title="HTTPS fehlt",
                description="Die finale URL nutzt kein HTTPS.",
                recommendation="HTTPS aktivieren und HTTP auf HTTPS weiterleiten.",
                evidence_url=evidence_url,
            )
        )
    if not title_ok:
        findings.append(
            _finding(
                finding_id="title_missing",
                category="seo",
                severity="minor",
                title="Seitentitel fehlt",
                description="Seitentitel wurde nicht erkannt.",
                recommendation="Einen eindeutigen <title> fuer die Seite setzen.",
                evidence_url=evidence_url,
            )
        )
    if not meta_description_ok:
        findings.append(
            _finding(
                finding_id="meta_description_missing",
                category="seo",
                severity="moderate",
                title="Meta Description fehlt",
                description="Meta Description wurde nicht erkannt.",
                recommendation="Eine aussagekraeftige Meta Description ergaenzen.",
                evidence_url=evidence_url,
            )
        )
    if not h1_ok:
        findings.append(
            _finding(
                finding_id="h1_missing",
                category="seo",
                severity="minor",
                title="H1 fehlt",
                description="H1 wurde nicht erkannt.",
                recommendation="Eine klare H1-Ueberschrift auf der Seite setzen.",
                evidence_url=evidence_url,
            )
        )
    if not html_lang_ok:
        findings.append(
            _finding(
                finding_id="html_lang_missing",
                category="accessibility",
                severity="minor",
                title="HTML lang fehlt",
                description="HTML lang Attribut wurde nicht erkannt.",
                recommendation="Das lang-Attribut am html-Element setzen.",
                evidence_url=evidence_url,
            )
        )
    if not impressum_ok:
        findings.append(
            _finding(
                finding_id="impressum_link_missing",
                category="privacy",
                severity="moderate",
                title="Impressum-Link fehlt",
                description="Impressum-Link wurde nicht erkannt.",
                recommendation="Einen klaren Impressum-Link in Navigation oder Footer setzen.",
                evidence_url=evidence_url,
            )
        )
    if not privacy_ok:
        findings.append(
            _finding(
                finding_id="privacy_link_missing",
                category="privacy",
                severity="moderate",
                title="Datenschutz-Link fehlt",
                description="Datenschutz-Link wurde nicht erkannt.",
                recommendation=(
                    "Einen klaren Link zur Datenschutzerklaerung in Navigation oder Footer setzen."
                ),
                evidence_url=evidence_url,
            )
        )
    if detected_trackers:
        joined = ", ".join(sorted(detected_trackers))
        findings.append(
            _finding(
                finding_id="known_trackers_detected",
                category="privacy",
                severity="info",
                title="Bekannte Tracker-Domains erkannt",
                description=f"Bekannte Tracker-Domains erkannt: {joined}.",
                recommendation="Tracker-Einbindung pruefen und datenschutzkonform konfigurieren.",
                evidence_url=evidence_url,
            )
        )
    return findings


def _build_summary(findings: list[dict[str, object]]) -> dict[str, int]:
    summary = {"critical": 0, "serious": 0, "moderate": 0, "minor": 0, "info": 0}
    for finding in findings:
        severity = str(finding.get("severity", "")).lower()
        if severity in summary:
            summary[severity] += 1
    return summary


def _build_checks(
    *,
    final_url: str,
    reachable: bool,
    https_ok: bool,
    title_ok: bool,
    meta_description_ok: bool,
    h1_ok: bool,
    html_lang_ok: bool,
    impressum_ok: bool,
    privacy_ok: bool,
    detected_trackers: list[str],
    findings: list[dict[str, object]],
) -> dict[str, object]:
    accessibility_findings = sum(
        1 for finding in findings if finding.get("category") == "accessibility"
    )
    return {
        "accessibility": {
            "label": "Barrierefreiheit",
            "status": "checked",
            "findingsCount": accessibility_findings,
        },
        "technical": {
            "label": "Technik",
            "https": https_ok,
            "reachable": reachable,
            "finalUrl": final_url,
        },
        "privacy": {
            "label": "Datenschutz-Hinweise",
            "impressumLink": impressum_ok,
            "privacyLink": privacy_ok,
            "detectedTrackers": sorted(detected_trackers),
        },
        "seo": {
            "label": "SEO-Grundlagen",
            "title": title_ok,
            "metaDescription": meta_description_ok,
            "h1": h1_ok,
            "htmlLang": html_lang_ok,
        },
    }


def _build_score(findings: list[dict[str, object]]) -> dict[str, int]:
    by_category = {"accessibility": 0, "technical": 0, "privacy": 0, "seo": 0}
    penalty_by_severity = {
        "critical": 50,
        "serious": 30,
        "moderate": 20,
        "minor": 10,
        "info": 5,
    }
    for finding in findings:
        category = str(finding.get("category", "")).lower()
        severity = str(finding.get("severity", "")).lower()
        if category in by_category:
            by_category[category] += penalty_by_severity.get(severity, 0)

    return {
        category: max(0, 100 - penalty)
        for category, penalty in by_category.items()
    }


def _finding(
    *,
    finding_id: str,
    category: str,
    severity: str,
    title: str,
    description: str,
    recommendation: str,
    evidence_url: str,
) -> dict[str, object]:
    return {
        "id": finding_id,
        "category": category,
        "severity": severity,
        "title": title,
        "description": description,
        "evidence": {
            "url": evidence_url,
            "selector": None,
            "snippet": None,
        },
        "recommendation": recommendation,
        "legalDisclaimer": FINDING_LEGAL_DISCLAIMER,
    }


def _detect_trackers(html: str) -> list[str]:
    lower = html.casefold()
    return [domain for domain in TRACKER_DOMAINS if domain in lower]


def _link_keyword_detected(
    links: list[tuple[str, str]],
    keywords: tuple[str, ...],
) -> bool:
    normalized_keywords = tuple(keyword.casefold() for keyword in keywords)
    for href, text in links:
        candidate = f"{href} {text}".casefold()
        if any(keyword in candidate for keyword in normalized_keywords):
            return True
    return False


class _QuickCheckHtmlParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title: str | None = None
        self.meta_description: str | None = None
        self.h1_text: str | None = None
        self.html_lang: str | None = None
        self.links: list[tuple[str, str]] = []

        self._in_title = False
        self._title_parts: list[str] = []
        self._in_h1 = False
        self._h1_parts: list[str] = []
        self._current_link_href: str | None = None
        self._current_link_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {key.lower(): (value or "") for key, value in attrs}
        lower_tag = tag.lower()
        if lower_tag == "html" and not self.html_lang:
            html_lang = attributes.get("lang", "").strip()
            if html_lang:
                self.html_lang = html_lang
        elif lower_tag == "title":
            self._in_title = True
            self._title_parts = []
        elif lower_tag == "h1":
            self._in_h1 = True
            self._h1_parts = []
        elif lower_tag == "meta":
            if self.meta_description:
                return
            name = attributes.get("name", "").strip().casefold()
            if name == "description":
                content = attributes.get("content", "").strip()
                if content:
                    self.meta_description = content
        elif lower_tag == "a":
            self._current_link_href = attributes.get("href", "").strip()
            self._current_link_parts = []

    def handle_endtag(self, tag: str) -> None:
        lower_tag = tag.lower()
        if lower_tag == "title":
            self._in_title = False
            title_text = "".join(self._title_parts).strip()
            if title_text and not self.title:
                self.title = title_text
        elif lower_tag == "h1":
            self._in_h1 = False
            h1_text = " ".join(part.strip() for part in self._h1_parts).strip()
            if h1_text and not self.h1_text:
                self.h1_text = " ".join(h1_text.split())
        elif lower_tag == "a":
            href = self._current_link_href or ""
            text = " ".join(part.strip() for part in self._current_link_parts).strip()
            if href or text:
                self.links.append((href, " ".join(text.split())))
            self._current_link_href = None
            self._current_link_parts = []

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self._title_parts.append(data)
        if self._in_h1:
            self._h1_parts.append(data)
        if self._current_link_href is not None:
            self._current_link_parts.append(data)
