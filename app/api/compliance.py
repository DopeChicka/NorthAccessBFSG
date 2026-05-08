from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.compliance_service import ScanNotFoundError, run_compliance_mapping

router = APIRouter(prefix="/compliance", tags=["compliance"])


@router.post("/run/{scan_id}")
def run_compliance(scan_id: str, db: Session = Depends(get_db)) -> dict[str, int | float | str]:
    try:
        summary = run_compliance_mapping(db, scan_id)
    except ScanNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Scan not found"
        ) from exc

    return summary.as_dict()
