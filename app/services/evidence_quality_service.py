from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models import Scan
from app.services.evidence_manifest_service import build_evidence_manifest_for_scan


class ScanNotFoundError(Exception):
    pass


def assess_scan_evidence_quality(db: Session, scan_id: str) -> dict[str, Any]:
    if db.get(Scan, scan_id) is None:
        raise ScanNotFoundError(f"Scan not found: {scan_id}")

    manifest = build_evidence_manifest_for_scan(db, scan_id)
    evidence_types: dict[str, int] = manifest["evidence_types"]
    evidence_count = manifest["evidence_count"]
    has_journey_evidence = _has_journey_evidence(evidence_types)
    has_axe_evidence = _has_axe_evidence(evidence_types)
    has_browser_smoke_evidence = evidence_types.get("browser_smoke", 0) > 0

    quality_status = _quality_status(
        evidence_count=evidence_count,
        has_journey_evidence=has_journey_evidence,
        has_axe_evidence=has_axe_evidence,
    )
    reasons = _quality_reasons(
        quality_status=quality_status,
        has_journey_evidence=has_journey_evidence,
        has_axe_evidence=has_axe_evidence,
        has_browser_smoke_evidence=has_browser_smoke_evidence,
    )

    return {
        "scan_id": scan_id,
        "evidence_count": evidence_count,
        "missing_hash_count": manifest["missing_hash_count"],
        "missing_related_entity_count": manifest["missing_related_entity_count"],
        "has_journey_evidence": has_journey_evidence,
        "has_axe_evidence": has_axe_evidence,
        "has_browser_smoke_evidence": has_browser_smoke_evidence,
        "quality_status": quality_status,
        "reasons": reasons,
        "no_legal_conclusion": True,
    }


def _has_journey_evidence(evidence_types: dict[str, int]) -> bool:
    for evidence_type, count in evidence_types.items():
        if count <= 0:
            continue
        if evidence_type.startswith("journey_"):
            return True
        if evidence_type == "axe_journey":
            return True
    return False


def _has_axe_evidence(evidence_types: dict[str, int]) -> bool:
    for evidence_type, count in evidence_types.items():
        if count <= 0:
            continue
        if evidence_type.startswith("axe_"):
            return True
    return False


def _quality_status(
    *,
    evidence_count: int,
    has_journey_evidence: bool,
    has_axe_evidence: bool,
) -> str:
    if evidence_count == 0:
        return "insufficient"
    if has_journey_evidence or has_axe_evidence:
        return "usable"
    return "partial"


def _quality_reasons(
    *,
    quality_status: str,
    has_journey_evidence: bool,
    has_axe_evidence: bool,
    has_browser_smoke_evidence: bool,
) -> list[str]:
    if quality_status == "insufficient":
        return ["no_evidence_available"]
    if quality_status == "usable":
        reasons: list[str] = []
        if has_axe_evidence:
            reasons.append("includes_axe_evidence")
        if has_journey_evidence:
            reasons.append("includes_journey_evidence")
        return reasons
    if has_browser_smoke_evidence:
        return ["browser_smoke_only"]
    return ["missing_axe_and_journey_evidence"]
