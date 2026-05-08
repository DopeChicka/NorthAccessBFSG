import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.core.celery import celery_app
from app.db.session import SessionLocal
from app.models import EvidenceBundle, Finding, Scan, ScanStatus
from app.services.evidence_service import persist_finding_evidence_refs, persist_scan_evidence
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
        scan.evidence_metadata = {}
        db.commit()

        logger.info("Started Playwright accessibility scan %s for %s", scan_id, domain)
        scan_result = run_accessibility_scan(domain)

        scan = db.get(Scan, scan_id)
        if scan is None:
            logger.warning("Scan %s disappeared before persistence", scan_id)
            return scan_id

        scan.status = ScanStatus.processing
        global_evidence_bundles = persist_scan_evidence(
            db, scan_id=scan_id, artifacts=scan_result.evidence_artifacts
        )
        scan.evidence_metadata = _with_evidence_bundle_metadata(
            scan_result.evidence_metadata, global_evidence_bundles
        )
        db.commit()

        _persist_findings(
            db,
            scan_id=scan_id,
            scan_result=scan_result,
            source_evidence_bundles=global_evidence_bundles,
        )

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
    db: Session,
    *,
    scan_id: str,
    scan_result: PlaywrightScanResult,
    source_evidence_bundles: list[EvidenceBundle],
) -> None:
    db.query(Finding).filter(Finding.scan_id == scan_id).delete(synchronize_session=False)
    db.flush()

    for engine_finding in scan_result.findings:
        finding = Finding(
            scan_id=scan_id,
            rule_id=engine_finding.rule_id,
            severity=engine_finding.severity,
            description=engine_finding.description,
            help_url=engine_finding.help_url,
            wcag_refs=engine_finding.wcag_refs,
            confidence_score=engine_finding.confidence_score,
            evidence_metadata=engine_finding.evidence_metadata,
        )
        db.add(finding)
        db.flush()

        finding_evidence_bundles = persist_finding_evidence_refs(
            db,
            scan_id=scan_id,
            finding_id=finding.id,
            source_bundles=source_evidence_bundles,
        )
        finding.evidence_metadata = _with_evidence_bundle_metadata(
            engine_finding.evidence_metadata, finding_evidence_bundles
        )

    db.commit()


def _with_evidence_bundle_metadata(
    metadata: dict[str, Any], bundles: list[EvidenceBundle]
) -> dict[str, Any]:
    return {
        **metadata,
        "evidence_bundles": [
            {
                "id": bundle.id,
                "type": bundle.type,
                "storage_backend": bundle.storage_backend,
                "storage_path": bundle.storage_path,
                "content_type": bundle.content_type,
                "size_bytes": bundle.size_bytes,
                "version": bundle.version,
                "hash": bundle.hash,
                "previous_hash": bundle.previous_hash,
                "chain_hash": bundle.chain_hash,
                "fingerprint": bundle.fingerprint,
            }
            for bundle in bundles
        ],
    }


def _mark_scan_failed(db: Session, scan_id: str, error: Exception) -> None:
    scan = db.get(Scan, scan_id)
    if scan is None:
        return

    scan.status = ScanStatus.failed
    scan.failed_at = datetime.now(UTC)
    scan.error_message = str(error)[:_MAX_ERROR_MESSAGE_LENGTH]
    db.commit()
