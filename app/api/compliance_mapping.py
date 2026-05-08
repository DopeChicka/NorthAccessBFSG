from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import ComplianceMapping
from app.services.compliance_mapping_service import (
    ComplianceMappingNotFoundError,
    FindingNotFoundError,
    ScanNotFoundError,
    get_finding_compliance,
    map_finding_compliance,
    map_scan_findings_compliance,
)

router = APIRouter(tags=["compliance-mapping"])


@router.post("/findings/{finding_id}/compliance/map")
def map_finding(
    finding_id: str, db: Session = Depends(get_db)
) -> dict[str, Any]:
    try:
        mapping = map_finding_compliance(db, finding_id)
    except FindingNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Finding not found"
        ) from exc

    return _serialize_mapping(mapping)


@router.get("/findings/{finding_id}/compliance")
def get_finding_mapping(
    finding_id: str, db: Session = Depends(get_db)
) -> dict[str, Any]:
    try:
        mapping = get_finding_compliance(db, finding_id)
    except FindingNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Finding not found"
        ) from exc
    except ComplianceMappingNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Compliance mapping not found",
        ) from exc

    return _serialize_mapping(mapping)


@router.post("/scans/{scan_id}/compliance/map")
def map_scan_findings(
    scan_id: str, db: Session = Depends(get_db)
) -> dict[str, Any]:
    try:
        mappings = map_scan_findings_compliance(db, scan_id)
    except ScanNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Scan not found"
        ) from exc

    return {
        "scan_id": scan_id,
        "mapped_count": len(mappings),
        "mappings": [_serialize_mapping(mapping) for mapping in mappings],
    }


def _serialize_mapping(mapping: ComplianceMapping) -> dict[str, Any]:
    return {
        "id": mapping.id,
        "finding_id": mapping.finding_id,
        "source_rule_id": mapping.source_rule_id,
        "wcag_refs": mapping.wcag_refs,
        "en_301_549_refs": mapping.en_301_549_refs,
        "bfsg_signal_refs": mapping.bfsg_signal_refs,
        "review_required": mapping.review_required,
        "confidence_score": mapping.confidence_score,
        "evidence": mapping.evidence,
        "created_at": mapping.created_at.isoformat() if mapping.created_at else None,
    }
