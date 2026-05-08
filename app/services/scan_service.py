from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.celery import celery_app
from app.models import Lead, Scan, ScanStatus

SCAN_TASK_NAME = "app.workers.scan_worker.run_scan"


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
        celery_app.send_task(SCAN_TASK_NAME, args=[scan.id])
    except Exception as exc:
        scan.status = ScanStatus.failed
        scan.failed_at = datetime.now(UTC)
        scan.error_message = "Could not enqueue scan task"
        db.commit()
        raise ScanQueueError("Could not enqueue scan task") from exc

    return scan
