import logging
import time
from datetime import UTC, datetime

from app.core.celery import celery_app
from app.db.session import SessionLocal
from app.models import Scan, ScanStatus

logger = logging.getLogger(__name__)


@celery_app.task(name="app.workers.scan_worker.run_scan")
def run_scan_task(scan_id: str) -> str:
    db = SessionLocal()
    try:
        scan = db.get(Scan, scan_id)
        if scan is None:
            logger.warning("Scan %s was not found; skipping task", scan_id)
            return scan_id

        scan.status = ScanStatus.running
        scan.started_at = datetime.now(UTC)
        db.commit()

        logger.info("Started placeholder accessibility scan %s", scan_id)
        time.sleep(2)

        scan.status = ScanStatus.done
        scan.completed_at = datetime.now(UTC)
        db.commit()

        logger.info("Completed placeholder accessibility scan %s", scan_id)
        return scan_id
    except Exception:
        db.rollback()
        _mark_scan_failed(db, scan_id)
        logger.exception("Scan task %s failed", scan_id)
        raise
    finally:
        db.close()


def _mark_scan_failed(db, scan_id: str) -> None:
    scan = db.get(Scan, scan_id)
    if scan is None:
        return

    scan.status = ScanStatus.failed
    scan.failed_at = datetime.now(UTC)
    db.commit()
