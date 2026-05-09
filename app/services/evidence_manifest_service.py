from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models import ScanEvidence


def build_evidence_manifest(db: Session, scan_id: str) -> dict[str, Any]:
    evidence_rows = (
        db.query(ScanEvidence)
        .filter(ScanEvidence.scan_id == scan_id)
        .order_by(ScanEvidence.created_at.asc(), ScanEvidence.id.asc())
        .all()
    )

    items = [
        {
            "evidence_id": evidence.id,
            "evidence_type": evidence.evidence_type,
            "path_or_key": evidence.path_or_key,
            "metadata": evidence.evidence_metadata,
            "hash": evidence.hash,
            "created_at": evidence.created_at.isoformat()
            if evidence.created_at
            else None,
        }
        for evidence in evidence_rows
    ]

    return {
        "scan_id": scan_id,
        "evidence_count": len(items),
        "items": items,
        "no_legal_conclusion": True,
    }
