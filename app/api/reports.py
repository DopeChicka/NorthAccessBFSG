from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Report
from app.services.report_service import (
    ReportNotFoundError,
    ScanNotFoundError,
    generate_scan_json_report,
    get_report,
    list_reports_for_scan,
)

router = APIRouter(tags=["reports"])


@router.post("/scans/{scan_id}/reports/json")
def create_scan_json_report(
    scan_id: str, db: Session = Depends(get_db)
) -> dict[str, Any]:
    try:
        report = generate_scan_json_report(db, scan_id)
    except ScanNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scan not found",
        ) from exc

    return _serialize_report(report)


@router.get("/reports/{report_id}")
def get_json_report(report_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        report = get_report(db, report_id)
    except ReportNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found",
        ) from exc

    return _serialize_report(report)


@router.get("/scans/{scan_id}/reports")
def list_scan_reports(
    scan_id: str, db: Session = Depends(get_db)
) -> dict[str, list[dict[str, Any]]]:
    try:
        reports = list_reports_for_scan(db, scan_id)
    except ScanNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scan not found",
        ) from exc

    return {"reports": [_serialize_report(report) for report in reports]}


def _serialize_report(report: Report) -> dict[str, Any]:
    return {
        "id": report.id,
        "scan_id": report.scan_id,
        "status": report.status.value,
        "report_type": report.report_type.value,
        "summary": report.summary,
        "output": report.output,
        "evidence_manifest": report.evidence_manifest,
        "created_at": report.created_at.isoformat() if report.created_at else None,
        "updated_at": report.updated_at.isoformat() if report.updated_at else None,
        "generated_at": report.generated_at.isoformat()
        if report.generated_at
        else None,
        "error_message": report.error_message,
    }
