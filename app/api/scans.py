from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.axe_homepage_service import (
    AxeHomepageAuditError,
    ScanNotFoundError as AxeScanNotFoundError,
    run_axe_homepage_audit,
)
from app.services.browser_smoke_service import (
    BrowserSmokeProbeError,
    ScanNotFoundError,
    run_browser_smoke_probe,
)
from app.services.evidence_quality_service import (
    ScanNotFoundError as EvidenceQualityScanNotFoundError,
    assess_scan_evidence_quality,
)
from app.services.review_finalization_service import (
    ScanNotFoundError as ReviewSummaryScanNotFoundError,
    summarize_scan_review_status,
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


@router.post("/{scan_id}/axe-homepage")
def run_axe_homepage(scan_id: str, db: Session = Depends(get_db)) -> dict[str, object]:
    try:
        evidence = run_axe_homepage_audit(db, scan_id)
    except AxeScanNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except AxeHomepageAuditError as exc:
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


@router.get("/{scan_id}/evidence/quality")
def get_scan_evidence_quality(
    scan_id: str, db: Session = Depends(get_db)
) -> dict[str, object]:
    try:
        return assess_scan_evidence_quality(db, scan_id)
    except EvidenceQualityScanNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.get("/{scan_id}/review/summary")
def get_scan_review_summary(
    scan_id: str, db: Session = Depends(get_db)
) -> dict[str, object]:
    try:
        return summarize_scan_review_status(db, scan_id)
    except ReviewSummaryScanNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
