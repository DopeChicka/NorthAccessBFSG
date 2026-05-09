from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models import Journey, JourneyStatus, Scan, ScanEvidence
from app.services.browser_smoke_service import (
    BrowserSmokeResult,
    BrowserSmokeRunner,
    _run_playwright_smoke,
)


class JourneyNotFoundError(Exception):
    pass


class JourneyExecutionError(Exception):
    pass


class ScanNotFoundError(Exception):
    pass


def execute_journey_smoke(
    db: Session,
    journey_id: str,
    *,
    runner: BrowserSmokeRunner | None = None,
) -> Journey:
    journey = db.get(Journey, journey_id)
    if journey is None:
        raise JourneyNotFoundError(f"Journey not found: {journey_id}")

    target_url = _target_url_for_journey(journey)
    if target_url is None:
        _mark_journey_failed(db, journey, "Journey has no URL for smoke execution")
        raise JourneyExecutionError("Journey has no URL for smoke execution")

    journey.status = JourneyStatus.running
    journey.error_message = None
    db.commit()

    try:
        result = (runner or _run_playwright_smoke)(target_url)
    except Exception as exc:
        _mark_journey_failed(db, journey, "Journey smoke execution failed")
        raise JourneyExecutionError("Journey smoke execution failed") from exc

    _create_journey_smoke_evidence(db, journey, result)
    journey.status = JourneyStatus.done
    journey.executed_at = datetime.now(UTC)
    journey.detected_url = result.final_url
    journey.evidence = {
        **(journey.evidence or {}),
        "journey_smoke": {
            "final_url": result.final_url,
            "http_status": result.http_status,
            "no_legal_conclusion": True,
        },
        "no_legal_conclusion": True,
    }
    db.commit()
    db.refresh(journey)
    return journey


def execute_scan_journeys_smoke(
    db: Session,
    scan_id: str,
    *,
    runner: BrowserSmokeRunner | None = None,
) -> list[Journey]:
    scan = db.get(Scan, scan_id)
    if scan is None:
        raise ScanNotFoundError(f"Scan not found: {scan_id}")

    journeys = _executable_journeys(db, scan_id)
    return [
        execute_journey_smoke(db, journey.id, runner=runner)
        for journey in journeys
    ]


def _create_journey_smoke_evidence(
    db: Session, journey: Journey, result: BrowserSmokeResult
) -> ScanEvidence:
    metadata = {
        "target_url": result.target_url,
        "final_url": result.final_url,
        "page_title": result.page_title,
        "http_status": result.http_status,
        "journey_type": journey.journey_type.value,
        "timestamp": result.captured_at,
        "no_crawling": True,
        "no_forms": True,
        "no_legal_conclusion": True,
    }
    evidence = ScanEvidence(
        scan_id=journey.scan_id,
        evidence_type="journey_smoke",
        related_entity_type="journey",
        related_entity_id=journey.id,
        path_or_key=f"scan-evidence/{journey.scan_id}/journeys/{journey.id}/smoke.json",
        evidence_metadata=metadata,
        hash=None,
    )
    db.add(evidence)
    db.flush()
    return evidence


def _executable_journeys(db: Session, scan_id: str) -> list[Journey]:
    return (
        db.query(Journey)
        .filter(
            Journey.scan_id == scan_id,
            Journey.status != JourneyStatus.skipped,
        )
        .order_by(Journey.journey_type.asc(), Journey.id.asc())
        .all()
    )


def _target_url_for_journey(journey: Journey) -> str | None:
    return journey.detected_url or journey.start_url


def _mark_journey_failed(db: Session, journey: Journey, message: str) -> None:
    journey.status = JourneyStatus.failed
    journey.error_message = message
    db.commit()
