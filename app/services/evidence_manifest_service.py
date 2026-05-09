from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from typing import Any

from sqlalchemy.orm import Session

from app.models import ScanEvidence


def build_evidence_manifest_for_scan(db: Session, scan_id: str) -> dict[str, Any]:
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
            "scan_id": evidence.scan_id,
            "related_entity_type": evidence.related_entity_type,
            "related_entity_id": evidence.related_entity_id,
            "storage_key": evidence.path_or_key,
            "path_or_key": evidence.path_or_key,
            "metadata": evidence.evidence_metadata,
            "hash": evidence.hash,
            "created_at": evidence.created_at.isoformat()
            if evidence.created_at
            else None,
            "no_legal_conclusion": True,
        }
        for evidence in evidence_rows
    ]
    missing_hash_count = sum(1 for item in items if item["hash"] is None)
    missing_related_entity_count = sum(
        1
        for item in items
        if item["related_entity_type"] is None or item["related_entity_id"] is None
    )
    evidence_types = _count_values(item["evidence_type"] for item in items)
    related_entity_types = _count_values(
        item["related_entity_type"] or "missing" for item in items
    )

    return {
        "scan_id": scan_id,
        "evidence_count": len(items),
        "missing_hash_count": missing_hash_count,
        "missing_related_entity_count": missing_related_entity_count,
        "evidence_types": evidence_types,
        "related_entity_types": related_entity_types,
        "items": items,
        "no_legal_conclusion": True,
    }


def build_evidence_manifest(db: Session, scan_id: str) -> dict[str, Any]:
    return build_evidence_manifest_for_scan(db, scan_id)


def _count_values(values: Iterable[str]) -> dict[str, int]:
    counts = Counter(values)
    return {key: counts[key] for key in sorted(counts)}
