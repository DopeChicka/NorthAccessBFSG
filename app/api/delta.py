from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import DeltaComparison
from app.services.delta_comparison_service import (
    BaselineScanNotFoundError,
    DeltaComparisonNotFoundError,
    TargetScanNotFoundError,
    generate_delta_comparison,
    get_delta_comparison,
    list_delta_comparisons_for_scan,
)

router = APIRouter(tags=["delta"])


@router.post("/scans/{target_scan_id}/delta/{baseline_scan_id}")
def create_delta_comparison(
    target_scan_id: str,
    baseline_scan_id: str,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        comparison = generate_delta_comparison(db, baseline_scan_id, target_scan_id)
    except BaselineScanNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Baseline scan not found",
        ) from exc
    except TargetScanNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target scan not found",
        ) from exc

    return _serialize_delta_comparison(comparison)


@router.get("/delta/{comparison_id}")
def get_delta(
    comparison_id: str, db: Session = Depends(get_db)
) -> dict[str, Any]:
    try:
        comparison = get_delta_comparison(db, comparison_id)
    except DeltaComparisonNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Delta comparison not found",
        ) from exc
    return _serialize_delta_comparison(comparison)


@router.get("/scans/{scan_id}/delta")
def list_scan_deltas(
    scan_id: str, db: Session = Depends(get_db)
) -> dict[str, list[dict[str, Any]]]:
    try:
        comparisons = list_delta_comparisons_for_scan(db, scan_id)
    except TargetScanNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scan not found",
        ) from exc

    return {"comparisons": [_serialize_delta_comparison(item) for item in comparisons]}


def _serialize_delta_comparison(comparison: DeltaComparison) -> dict[str, Any]:
    return {
        "id": comparison.id,
        "baseline_scan_id": comparison.baseline_scan_id,
        "target_scan_id": comparison.target_scan_id,
        "status": comparison.status.value,
        "summary": comparison.summary,
        "output": comparison.output,
        "created_at": comparison.created_at.isoformat()
        if comparison.created_at
        else None,
        "updated_at": comparison.updated_at.isoformat()
        if comparison.updated_at
        else None,
        "generated_at": comparison.generated_at.isoformat()
        if comparison.generated_at
        else None,
        "error_message": comparison.error_message,
    }
