import logging
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.celery import celery_app
from app.db.session import SessionLocal
from app.models import Finding, Scan, ScanStatus
from app.workers.playwright_engine import PlaywrightScanResult, run_accessibility_scan

logger = logging.getLogger(__name__)
_MAX_ERROR_MESSAGE_LENGTH = 4000


@celery_app.task(name="app.workers.scan_worker.run_scan")
def run_scan_task(scan_id: str) -> str:
    db = SessionLocal()
    try:
        scan = db.get(Scan, scan_id)
        if scan is None:
            logger.warning("Scan %s was not found; skipping task", scan_id)
            return scan_id

        domain = scan.lead.domain
        scan.status = ScanStatus.running
        scan.started_at = datetime.now(UTC)
        scan.completed_at = None
        scan.failed_at = None
        scan.error_message = None
        db.commit()

        logger.info("Started Playwright accessibility scan %s for %s", scan_id, domain)
        scan_result = run_accessibility_scan(domain)

        scan = db.get(Scan, scan_id)
        if scan is None:
            logger.warning("Scan %s disappeared before persistence", scan_id)
            return scan_id

        scan.status = ScanStatus.processing
        db.commit()

        _persist_findings(db, scan_id=scan_id, scan_result=scan_result)

        scan = db.get(Scan, scan_id)
        if scan is not None:
            scan.status = ScanStatus.done
            scan.completed_at = datetime.now(UTC)
            scan.error_message = None
            db.commit()

        logger.info(
            "Completed Playwright accessibility scan %s with %s findings",
            scan_id,
            len(scan_result.findings),
        )
        return scan_id
    except Exception as exc:
        db.rollback()
        _mark_scan_failed(db, scan_id, exc)
        logger.exception("Scan task %s failed", scan_id)
        raise
    finally:
        db.close()


def _persist_findings(
    db: Session, *, scan_id: str, scan_result: PlaywrightScanResult
) -> None:
    db.query(Finding).filter(Finding.scan_id == scan_id).delete(synchronize_session=False)

    for engine_finding in scan_result.findings:
        db.add(
            Finding(
                scan_id=scan_id,
                rule_id=engine_finding.rule_id,
                severity=engine_finding.severity,
                description=engine_finding.description,
                help_url=engine_finding.help_url,
                wcag_refs=engine_finding.wcag_refs,
                confidence_score=engine_finding.confidence_score,
                evidence_metadata=engine_finding.evidence_metadata,
            )
        )

    db.commit()


def _mark_scan_failed(db: Session, scan_id: str, error: Exception) -> None:
    scan = db.get(Scan, scan_id)
    if scan is None:
        return

    scan.status = ScanStatus.failed
    scan.failed_at = datetime.now(UTC)
    scan.error_message = str(error)[:_MAX_ERROR_MESSAGE_LENGTH]
    db.commit()
