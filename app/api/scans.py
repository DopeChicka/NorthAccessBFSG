from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.browser_smoke_service import (
    BrowserSmokeProbeError,
    ScanNotFoundError,
    run_browser_smoke_probe,
)
from app.services.scan_service import LeadNotFoundError, ScanQueueError, create_scan_job

router = APIRouter(prefix="/scans", tags=["scans"])


@router.post("/run/{lead_id}", status_code=status.HTTP_202_ACCEPTED)
def run_scan(lead_id: str, db: Session = Depends(get_db)) -> dict[str, str]:
    try:
        scan = create_scan_job(db, lead_id)
    except LeadNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found"
        ) from exc
    except ScanQueueError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Scan queue is unavailable",
        ) from exc

    return {"scan_id": scan.id}


@router.post("/{scan_id}/browser-smoke")
def run_browser_smoke(scan_id: str, db: Session = Depends(get_db)) -> dict[str, object]:
    try:
        evidence = run_browser_smoke_probe(db, scan_id)
    except ScanNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except BrowserSmokeProbeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return {
        "scan_id": evidence.scan_id,
        "evidence_id": evidence.id,
        "evidence_type": evidence.evidence_type,
        "path_or_key": evidence.path_or_key,
        "metadata": evidence.evidence_metadata,
    }
