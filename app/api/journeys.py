from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Journey
from app.services.journey_planning_service import (
    ScanNotFoundError,
    list_scan_journeys,
    plan_scan_journeys,
)

router = APIRouter(tags=["journeys"])


@router.post("/scans/{scan_id}/journeys/plan")
def plan_journeys(scan_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        journeys = plan_scan_journeys(db, scan_id)
    except ScanNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scan not found",
        ) from exc
    return {"journeys": [_serialize_journey(journey) for journey in journeys]}


@router.get("/scans/{scan_id}/journeys")
def list_journeys(scan_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        journeys = list_scan_journeys(db, scan_id)
    except ScanNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scan not found",
        ) from exc
    return {"journeys": [_serialize_journey(journey) for journey in journeys]}


def _serialize_journey(journey: Journey) -> dict[str, Any]:
    return {
        "id": journey.id,
        "scan_id": journey.scan_id,
        "journey_type": journey.journey_type.value,
        "status": journey.status.value,
        "start_url": journey.start_url,
        "detected_url": journey.detected_url,
        "signals": journey.signals,
        "evidence": journey.evidence,
        "created_at": journey.created_at.isoformat() if journey.created_at else None,
        "updated_at": journey.updated_at.isoformat() if journey.updated_at else None,
    }
