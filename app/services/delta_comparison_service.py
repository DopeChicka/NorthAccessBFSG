from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models import DeltaComparison, DeltaComparisonStatus, Finding, Scan
from app.services.finding_fingerprint_service import build_finding_fingerprint


class BaselineScanNotFoundError(Exception):
    pass


class TargetScanNotFoundError(Exception):
    pass


class DeltaComparisonNotFoundError(Exception):
    pass


def generate_delta_comparison(
    db: Session, baseline_scan_id: str, target_scan_id: str
) -> DeltaComparison:
    baseline_scan = db.get(Scan, baseline_scan_id)
    if baseline_scan is None:
        raise BaselineScanNotFoundError(f"Baseline scan not found: {baseline_scan_id}")

    target_scan = db.get(Scan, target_scan_id)
    if target_scan is None:
        raise TargetScanNotFoundError(f"Target scan not found: {target_scan_id}")

    comparison = DeltaComparison(
        baseline_scan_id=baseline_scan_id,
        target_scan_id=target_scan_id,
        status=DeltaComparisonStatus.pending,
        summary={},
        output={},
    )
    db.add(comparison)
    db.flush()

    try:
        baseline_entries = _fingerprinted_findings(db, baseline_scan_id)
        target_entries = _fingerprinted_findings(db, target_scan_id)
        baseline_by_fingerprint = {
            entry["fingerprint"]: entry for entry in baseline_entries
        }
        target_by_fingerprint = {entry["fingerprint"]: entry for entry in target_entries}

        baseline_fingerprints = set(baseline_by_fingerprint)
        target_fingerprints = set(target_by_fingerprint)
        new_fingerprints = sorted(target_fingerprints - baseline_fingerprints)
        resolved_fingerprints = sorted(baseline_fingerprints - target_fingerprints)
        unchanged_fingerprints = sorted(baseline_fingerprints & target_fingerprints)

        output = {
            "comparison_id": comparison.id,
            "baseline_scan_id": baseline_scan_id,
            "target_scan_id": target_scan_id,
            "new_findings": [
                target_by_fingerprint[fingerprint] for fingerprint in new_fingerprints
            ],
            "resolved_findings": [
                baseline_by_fingerprint[fingerprint]
                for fingerprint in resolved_fingerprints
            ],
            "unchanged_findings": [
                {
                    "baseline": baseline_by_fingerprint[fingerprint],
                    "target": target_by_fingerprint[fingerprint],
                    "fingerprint": fingerprint,
                }
                for fingerprint in unchanged_fingerprints
            ],
            "no_legal_conclusion": True,
        }
        summary = {
            "baseline_finding_count": len(baseline_entries),
            "target_finding_count": len(target_entries),
            "new_count": len(new_fingerprints),
            "resolved_count": len(resolved_fingerprints),
            "unchanged_count": len(unchanged_fingerprints),
            "no_legal_conclusion": True,
        }
        comparison.status = DeltaComparisonStatus.generated
        comparison.summary = summary
        comparison.output = output
        comparison.generated_at = datetime.now(UTC)
        comparison.error_message = None
    except Exception as exc:
        comparison.status = DeltaComparisonStatus.failed
        comparison.error_message = "Delta comparison generation failed"
        db.commit()
        raise RuntimeError("Delta comparison generation failed") from exc

    db.commit()
    db.refresh(comparison)
    return comparison


def get_delta_comparison(db: Session, comparison_id: str) -> DeltaComparison:
    comparison = db.get(DeltaComparison, comparison_id)
    if comparison is None:
        raise DeltaComparisonNotFoundError(
            f"Delta comparison not found: {comparison_id}"
        )
    return comparison


def list_delta_comparisons_for_scan(db: Session, scan_id: str) -> list[DeltaComparison]:
    scan = db.get(Scan, scan_id)
    if scan is None:
        raise TargetScanNotFoundError(f"Scan not found: {scan_id}")

    return (
        db.query(DeltaComparison)
        .filter(
            or_(
                DeltaComparison.baseline_scan_id == scan_id,
                DeltaComparison.target_scan_id == scan_id,
            )
        )
        .order_by(DeltaComparison.created_at.desc(), DeltaComparison.id.desc())
        .all()
    )


def _fingerprinted_findings(db: Session, scan_id: str) -> list[dict[str, Any]]:
    findings = (
        db.query(Finding)
        .filter(Finding.scan_id == scan_id)
        .order_by(Finding.created_at.asc(), Finding.id.asc())
        .all()
    )
    return [_serialize_finding_delta_entry(finding) for finding in findings]


def _serialize_finding_delta_entry(finding: Finding) -> dict[str, Any]:
    return {
        "finding_id": finding.id,
        "rule_id": finding.rule_id,
        "severity": finding.severity,
        "fingerprint": build_finding_fingerprint(finding),
        "evidence": _compact_evidence(finding),
        "no_legal_conclusion": True,
    }


def _compact_evidence(finding: Finding) -> dict[str, Any]:
    evidence = finding.evidence or finding.evidence_metadata or {}
    compact: dict[str, Any] = {}
    for key in (
        "target_url",
        "final_url",
        "impact",
        "node_count",
        "sample_targets",
        "selector",
        "target",
    ):
        if key in evidence:
            compact[key] = evidence[key]
    compact["no_legal_conclusion"] = True
    return compact
