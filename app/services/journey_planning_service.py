from __future__ import annotations

from urllib.parse import urlparse

from sqlalchemy.orm import Session

from app.models import (
    Journey,
    JourneyStatus,
    JourneyType,
    LeadCandidate,
    Scan,
    WebsiteProbe,
)


class ScanNotFoundError(Exception):
    pass


def plan_scan_journeys(db: Session, scan_id: str) -> list[Journey]:
    scan = db.get(Scan, scan_id)
    if scan is None:
        raise ScanNotFoundError(f"Scan not found: {scan_id}")

    candidate = _candidate_for_scan(db, scan)
    probe = _latest_website_probe(db, candidate.id if candidate else None)
    start_url = _start_url(scan, candidate, probe)
    specs = _journey_specs(start_url, candidate, probe)
    journeys = [_upsert_journey(db, scan_id, spec) for spec in specs]
    db.commit()
    for journey in journeys:
        db.refresh(journey)
    return journeys


def list_scan_journeys(db: Session, scan_id: str) -> list[Journey]:
    scan = db.get(Scan, scan_id)
    if scan is None:
        raise ScanNotFoundError(f"Scan not found: {scan_id}")

    return (
        db.query(Journey)
        .filter(Journey.scan_id == scan_id)
        .order_by(Journey.journey_type.asc(), Journey.id.asc())
        .all()
    )


def _journey_specs(
    start_url: str | None,
    candidate: LeadCandidate | None,
    probe: WebsiteProbe | None,
) -> list[dict[str, object]]:
    base_signals = _signals(candidate, probe)
    specs = [
        _spec(
            JourneyType.homepage,
            JourneyStatus.ready if start_url else JourneyStatus.skipped,
            start_url,
            base_signals,
            "homepage_available" if start_url else "missing_start_url",
        )
    ]

    has_transaction_signal = bool(
        probe
        and (
            probe.has_shop_signal
            or probe.has_checkout_signal
            or probe.has_b2c_transaction_signal
        )
    )
    if has_transaction_signal:
        for journey_type in (JourneyType.shop, JourneyType.cart, JourneyType.checkout):
            specs.append(
                _spec(
                    journey_type,
                    JourneyStatus.ready,
                    start_url,
                    base_signals,
                    "transaction_signal_detected",
                )
            )

    if probe and probe.has_booking_signal:
        specs.append(
            _spec(
                JourneyType.booking,
                JourneyStatus.ready,
                start_url,
                base_signals,
                "booking_signal_detected",
            )
        )

    if probe and probe.has_login_signal:
        specs.append(
            _spec(
                JourneyType.login,
                JourneyStatus.ready,
                start_url,
                base_signals,
                "login_signal_detected",
            )
        )

    for placeholder_type in (JourneyType.search, JourneyType.contact_form):
        specs.append(
            _spec(
                placeholder_type,
                JourneyStatus.skipped,
                start_url,
                base_signals,
                "signal_not_detected",
            )
        )

    return sorted(specs, key=lambda item: _journey_sort_key(item["journey_type"]))


def _spec(
    journey_type: JourneyType,
    status: JourneyStatus,
    start_url: str | None,
    signals: dict[str, object],
    reason: str,
) -> dict[str, object]:
    return {
        "journey_type": journey_type,
        "status": status,
        "start_url": start_url,
        "detected_url": start_url if status == JourneyStatus.ready else None,
        "signals": signals,
        "evidence": {
            "source": "journey_planning",
            "reason": reason,
            "no_live_crawling": True,
            "no_legal_conclusion": True,
        },
    }


def _upsert_journey(
    db: Session, scan_id: str, spec: dict[str, object]
) -> Journey:
    journey = (
        db.query(Journey)
        .filter(
            Journey.scan_id == scan_id,
            Journey.journey_type == spec["journey_type"],
        )
        .one_or_none()
    )
    if journey is None:
        journey = Journey(scan_id=scan_id, journey_type=spec["journey_type"])
        db.add(journey)
        db.flush()

    journey.status = spec["status"]
    journey.start_url = spec["start_url"]
    journey.detected_url = spec["detected_url"]
    journey.signals = spec["signals"]
    journey.evidence = spec["evidence"]
    return journey


def _candidate_for_scan(db: Session, scan: Scan) -> LeadCandidate | None:
    candidate_id = (scan.evidence_metadata or {}).get("lead_candidate_id")
    if not candidate_id:
        return None
    return db.get(LeadCandidate, candidate_id)


def _latest_website_probe(
    db: Session, candidate_id: str | None
) -> WebsiteProbe | None:
    if not candidate_id:
        return None
    return (
        db.query(WebsiteProbe)
        .filter(WebsiteProbe.lead_candidate_id == candidate_id)
        .order_by(WebsiteProbe.created_at.desc(), WebsiteProbe.id.desc())
        .first()
    )


def _start_url(
    scan: Scan,
    candidate: LeadCandidate | None,
    probe: WebsiteProbe | None,
) -> str | None:
    for value in (
        probe.url if probe else None,
        candidate.domain if candidate else None,
        probe.normalized_domain if probe else None,
        scan.lead.domain if scan.lead else None,
    ):
        normalized = _normalize_url(value)
        if normalized:
            return normalized
    return None


def _normalize_url(value: str | None) -> str | None:
    if not value or not value.strip():
        return None
    item = value.strip()
    if urlparse(item).scheme:
        return item
    return f"https://{item}"


def _signals(
    candidate: LeadCandidate | None, probe: WebsiteProbe | None
) -> dict[str, object]:
    return {
        "candidate_id": candidate.id if candidate else None,
        "category": candidate.category if candidate else None,
        "website_probe_id": probe.id if probe else None,
        "has_homepage_signal": probe.has_homepage_signal if probe else None,
        "has_login_signal": probe.has_login_signal if probe else None,
        "has_shop_signal": probe.has_shop_signal if probe else None,
        "has_booking_signal": probe.has_booking_signal if probe else None,
        "has_checkout_signal": probe.has_checkout_signal if probe else None,
        "has_b2c_transaction_signal": (
            probe.has_b2c_transaction_signal if probe else None
        ),
        "no_legal_conclusion": True,
    }


def _journey_sort_key(journey_type: JourneyType) -> int:
    order = {
        JourneyType.homepage: 0,
        JourneyType.shop: 1,
        JourneyType.cart: 2,
        JourneyType.checkout: 3,
        JourneyType.booking: 4,
        JourneyType.login: 5,
        JourneyType.search: 6,
        JourneyType.contact_form: 7,
    }
    return order[journey_type]
