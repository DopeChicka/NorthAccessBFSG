from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.discovery.keywords import get_keyword_groups
from app.discovery.place_resolver import PlaceDataError, PlaceNotFoundError, resolve_city
from app.models.discovery_run import DiscoveryRun
from app.models.lead_candidate import LeadCandidate
from app.services.discovery_service import (
    DiscoveryRunNotFoundError,
    create_discovery_run,
    get_discovery_run,
    list_lead_candidates,
)

router = APIRouter(prefix="/discovery", tags=["discovery"])


def _format_datetime(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _serialize_discovery_run(discovery_run: DiscoveryRun) -> dict[str, Any]:
    return {
        "id": discovery_run.id,
        "city": discovery_run.city,
        "normalized_city": discovery_run.normalized_city,
        "status": discovery_run.status.value,
        "postal_codes": discovery_run.postal_codes,
        "keyword_groups": discovery_run.keyword_groups,
        "query_plan": discovery_run.query_plan,
        "created_at": _format_datetime(discovery_run.created_at),
        "completed_at": _format_datetime(discovery_run.completed_at),
        "error_message": discovery_run.error_message,
    }


def _serialize_candidate(candidate: LeadCandidate) -> dict[str, Any]:
    return {
        "id": candidate.id,
        "discovery_run_id": candidate.discovery_run_id,
        "source": candidate.source,
        "source_reference": candidate.source_reference,
        "company_name": candidate.company_name,
        "domain": candidate.domain,
        "city": candidate.city,
        "postal_code": candidate.postal_code,
        "address": candidate.address,
        "phone": candidate.phone,
        "category": candidate.category,
        "raw_data": candidate.raw_data,
        "confidence_score": candidate.confidence_score,
        "created_at": _format_datetime(candidate.created_at),
    }


@router.get("/places/{city}")
def get_places(city: str) -> dict[str, object]:
    try:
        matches = resolve_city(city)
    except PlaceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except PlaceDataError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    return {"city": city, "matches": [match.to_dict() for match in matches]}


@router.get("/keywords")
def get_keywords() -> dict[str, object]:
    return {"groups": get_keyword_groups()}


@router.post("/runs/{city}")
def create_run(city: str, db: Session = Depends(get_db)) -> dict[str, object]:
    try:
        discovery_run = create_discovery_run(db, city)
    except PlaceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except PlaceDataError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    return {
        "discovery_run_id": discovery_run.id,
        "city": discovery_run.city,
        "status": discovery_run.status.value,
        "postal_codes_count": len(discovery_run.postal_codes),
        "query_count": len(discovery_run.query_plan),
    }


@router.get("/runs/{run_id}")
def read_run(run_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        discovery_run = get_discovery_run(db, run_id)
    except DiscoveryRunNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _serialize_discovery_run(discovery_run)


@router.get("/runs/{run_id}/candidates")
def read_run_candidates(run_id: str, db: Session = Depends(get_db)) -> dict[str, object]:
    try:
        candidates = list_lead_candidates(db, run_id)
    except DiscoveryRunNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return {"discovery_run_id": run_id, "candidates": [_serialize_candidate(candidate) for candidate in candidates]}
