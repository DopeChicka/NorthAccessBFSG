from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models import Lead, Scan, ScanStatus
from app.workers.scan_worker import run_scan_task


class LeadNotFoundError(Exception):
    pass


class ScanQueueError(Exception):
    pass


def create_scan_job(db: Session, lead_id: str) -> Scan:
    lead = db.get(Lead, lead_id)
    if lead is None:
        raise LeadNotFoundError(f"Lead {lead_id} was not found")

    scan = Scan(lead_id=lead.id, status=ScanStatus.pending)
    db.add(scan)
    db.commit()
    db.refresh(scan)

    try:
        run_scan_task.delay(scan.id)
    except Exception as exc:
        scan.status = ScanStatus.failed
        scan.failed_at = datetime.now(UTC)
        db.commit()
        raise ScanQueueError("Could not enqueue scan task") from exc

    return scan
