from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Finding, Scan
from app.services.evidence_service import list_finding_evidence, list_scan_evidence

router = APIRouter(prefix="/evidence", tags=["evidence"])


@router.get("/scan/{scan_id}")
def get_scan_evidence(scan_id: str, db: Session = Depends(get_db)) -> dict[str, object]:
    if db.get(Scan, scan_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Scan not found"
        )

    evidence = [bundle.as_dict() for bundle in list_scan_evidence(db, scan_id)]
    return {"scan_id": scan_id, "evidence": evidence}


@router.get("/finding/{finding_id}")
def get_finding_evidence(finding_id: str, db: Session = Depends(get_db)) -> dict[str, object]:
    if db.get(Finding, finding_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Finding not found"
        )

    evidence = [bundle.as_dict() for bundle in list_finding_evidence(db, finding_id)]
    return {"finding_id": finding_id, "evidence": evidence}
