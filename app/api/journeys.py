from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Journey
from app.services.axe_journey_service import (
    AxeJourneyAuditError,
    JourneyNotFoundError as AxeJourneyNotFoundError,
    ScanNotFoundError as AxeScanNotFoundError,
    run_axe_for_journey,
    run_axe_for_scan_journeys,
)
from app.services.journey_execution_service import (
    JourneyExecutionError,
    JourneyNotFoundError,
    ScanNotFoundError as JourneyExecutionScanNotFoundError,
    execute_journey_smoke,
    execute_scan_journeys_smoke,
)
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


@router.post("/journeys/{journey_id}/execute-smoke")
def execute_smoke(journey_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        journey = execute_journey_smoke(db, journey_id)
    except JourneyNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Journey not found",
        ) from exc
    except JourneyExecutionError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return _serialize_journey(journey)


@router.post("/scans/{scan_id}/journeys/execute-smoke")
def execute_scan_smoke(scan_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        journeys = execute_scan_journeys_smoke(db, scan_id)
    except JourneyExecutionScanNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scan not found",
        ) from exc
    except JourneyExecutionError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return {"journeys": [_serialize_journey(journey) for journey in journeys]}


@router.post("/journeys/{journey_id}/axe")
def run_journey_axe(journey_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        findings = run_axe_for_journey(db, journey_id)
    except AxeJourneyNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Journey not found",
        ) from exc
    except AxeJourneyAuditError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return {
        "journey_id": journey_id,
        "finding_count": len(findings),
        "findings": [_serialize_finding(finding) for finding in findings],
        "no_legal_conclusion": True,
    }


@router.post("/scans/{scan_id}/journeys/axe")
def run_scan_journeys_axe(scan_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        findings = run_axe_for_scan_journeys(db, scan_id)
    except AxeScanNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scan not found",
        ) from exc
    except AxeJourneyAuditError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return {
        "scan_id": scan_id,
        "finding_count": len(findings),
        "findings": [_serialize_finding(finding) for finding in findings],
        "no_legal_conclusion": True,
    }


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
        "executed_at": journey.executed_at.isoformat() if journey.executed_at else None,
        "error_message": journey.error_message,
    }


def _serialize_finding(finding) -> dict[str, Any]:
    return {
        "id": finding.id,
        "scan_id": finding.scan_id,
        "journey_id": finding.journey_id,
        "rule_id": finding.rule_id,
        "severity": finding.severity,
        "description": finding.description,
        "wcag_refs": finding.wcag_refs,
        "evidence": finding.evidence,
        "no_legal_conclusion": True,
    }
