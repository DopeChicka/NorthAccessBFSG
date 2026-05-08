from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.discovery.keywords import get_keyword_groups
from app.discovery.place_resolver import PlaceDataError, PlaceNotFoundError, resolve_city
from app.discovery.providers.google_places_provider import (
    GooglePlacesConfigurationError,
    GooglePlacesDisabledError,
)
from app.models.company_enrichment import CompanyEnrichment
from app.models.company_qualification import CompanyQualification
from app.models.discovery_run import DiscoveryRun
from app.models.lead_candidate import LeadCandidate
from app.models.promotion_decision import PromotionDecision
from app.models.scan import Scan
from app.models.scan_readiness_decision import ScanReadinessDecision
from app.models.website_probe import WebsiteProbe
from app.services.company_enrichment_service import (
    enrich_candidate_with_mock,
    get_latest_enrichment,
)
from app.services.company_qualification_service import (
    LeadCandidateNotFoundError,
    create_candidate_precheck,
    get_latest_candidate_qualification,
)
from app.services.discovery_service import (
    DiscoveryRunNotFoundError,
    create_discovery_run,
    get_discovery_run,
    list_lead_candidates,
)
from app.services.promotion_service import (
    evaluate_candidate_for_promotion,
    get_latest_promotion_decision,
)
from app.services.provider_execution_service import (
    execute_google_places_provider,
    execute_mock_provider,
)
from app.services.scan_readiness_service import (
    ScanReadinessNotReadyError,
    create_scan_skeleton_for_candidate,
    evaluate_candidate_for_scan_readiness,
    get_latest_scan_readiness_decision,
)
from app.services.website_probe_service import (
    get_latest_website_probe,
    run_live_website_probe,
    run_mock_website_probe,
)
from app.website_probe.providers.http_provider import LiveWebsiteProbeDisabledError

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


def _serialize_enrichment(enrichment: CompanyEnrichment) -> dict[str, Any]:
    return {
        "id": enrichment.id,
        "candidate_id": enrichment.lead_candidate_id,
        "source": enrichment.source,
        "source_reference": enrichment.source_reference,
        "company_name": enrichment.company_name,
        "legal_form": enrichment.legal_form,
        "registry_id": enrichment.registry_id,
        "source_url": enrichment.source_url,
        "employee_count": enrichment.employee_count,
        "annual_revenue_eur": enrichment.annual_revenue_eur,
        "balance_sheet_total_eur": enrichment.balance_sheet_total_eur,
        "raw_data": enrichment.raw_data,
        "confidence_score": enrichment.confidence_score,
        "created_at": _format_datetime(enrichment.created_at),
        "updated_at": _format_datetime(enrichment.updated_at),
    }


def _serialize_qualification(qualification: CompanyQualification) -> dict[str, Any]:
    return {
        "id": qualification.id,
        "candidate_id": qualification.lead_candidate_id,
        "status": qualification.status.value,
        "company_name": qualification.company_name,
        "legal_form": qualification.legal_form,
        "registry_id": qualification.registry_id,
        "northdata_url": qualification.northdata_url,
        "employee_count": qualification.employee_count,
        "annual_revenue_eur": qualification.annual_revenue_eur,
        "balance_sheet_total_eur": qualification.balance_sheet_total_eur,
        "is_microenterprise": qualification.is_microenterprise,
        "b2c_signal": qualification.b2c_signal,
        "bfsg_category_signal": qualification.bfsg_category_signal,
        "website_signal": qualification.website_signal,
        "confidence_score": qualification.confidence_score,
        "evidence": qualification.evidence,
        "notes": qualification.notes,
        "created_at": _format_datetime(qualification.created_at),
        "updated_at": _format_datetime(qualification.updated_at),
    }


def _serialize_promotion_decision(decision: PromotionDecision) -> dict[str, Any]:
    return {
        "id": decision.id,
        "candidate_id": decision.lead_candidate_id,
        "company_qualification_id": decision.company_qualification_id,
        "company_enrichment_id": decision.company_enrichment_id,
        "status": decision.status.value,
        "reason_code": decision.reason_code,
        "reasons": decision.reasons,
        "confidence_score": decision.confidence_score,
        "created_at": _format_datetime(decision.created_at),
        "updated_at": _format_datetime(decision.updated_at),
    }


def _serialize_website_probe(probe: WebsiteProbe) -> dict[str, Any]:
    return {
        "id": probe.id,
        "candidate_id": probe.lead_candidate_id,
        "promotion_decision_id": probe.promotion_decision_id,
        "url": probe.url,
        "normalized_domain": probe.normalized_domain,
        "status": probe.status.value,
        "http_status": probe.http_status,
        "has_homepage_signal": probe.has_homepage_signal,
        "has_impressum_signal": probe.has_impressum_signal,
        "has_login_signal": probe.has_login_signal,
        "has_shop_signal": probe.has_shop_signal,
        "has_booking_signal": probe.has_booking_signal,
        "has_checkout_signal": probe.has_checkout_signal,
        "has_b2c_transaction_signal": probe.has_b2c_transaction_signal,
        "evidence": probe.evidence,
        "confidence_score": probe.confidence_score,
        "created_at": _format_datetime(probe.created_at),
        "updated_at": _format_datetime(probe.updated_at),
    }


def _serialize_scan_readiness_decision(
    decision: ScanReadinessDecision,
) -> dict[str, Any]:
    return {
        "id": decision.id,
        "candidate_id": decision.lead_candidate_id,
        "promotion_decision_id": decision.promotion_decision_id,
        "website_probe_id": decision.website_probe_id,
        "status": decision.status.value,
        "reason_code": decision.reason_code,
        "reasons": decision.reasons,
        "confidence_score": decision.confidence_score,
        "created_at": _format_datetime(decision.created_at),
        "updated_at": _format_datetime(decision.updated_at),
    }


def _serialize_scan_skeleton(scan: Scan) -> dict[str, Any]:
    return {
        "scan_id": scan.id,
        "lead_id": scan.lead_id,
        "status": scan.status.value,
        "evidence_metadata": scan.evidence_metadata,
        "created_at": _format_datetime(scan.created_at),
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


@router.post("/runs/{run_id}/providers/mock")
def run_mock_provider(run_id: str, db: Session = Depends(get_db)) -> dict[str, str | int]:
    try:
        summary = execute_mock_provider(db, run_id)
    except DiscoveryRunNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return summary.to_dict()


@router.post("/runs/{run_id}/providers/google-places")
def run_google_places_provider(
    run_id: str, db: Session = Depends(get_db)
) -> dict[str, str | int]:
    try:
        summary = execute_google_places_provider(db, run_id)
    except DiscoveryRunNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except GooglePlacesDisabledError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    except GooglePlacesConfigurationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return summary.to_dict()


@router.get("/runs/{run_id}/candidates")
def read_run_candidates(run_id: str, db: Session = Depends(get_db)) -> dict[str, object]:
    try:
        candidates = list_lead_candidates(db, run_id)
    except DiscoveryRunNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return {
        "discovery_run_id": run_id,
        "candidates": [_serialize_candidate(candidate) for candidate in candidates],
    }


@router.post("/candidates/{candidate_id}/enrichment/mock")
def run_mock_company_enrichment(
    candidate_id: str, db: Session = Depends(get_db)
) -> dict[str, str | float | None]:
    try:
        summary = enrich_candidate_with_mock(db, candidate_id)
    except LeadCandidateNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return summary.to_dict()


@router.get("/candidates/{candidate_id}/enrichment")
def read_candidate_enrichment(
    candidate_id: str, db: Session = Depends(get_db)
) -> dict[str, object]:
    try:
        enrichment = get_latest_enrichment(db, candidate_id)
    except LeadCandidateNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    if enrichment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Company enrichment not found for candidate: {candidate_id}",
        )
    return _serialize_enrichment(enrichment)


@router.post("/candidates/{candidate_id}/qualification/precheck")
def run_candidate_qualification_precheck(
    candidate_id: str, db: Session = Depends(get_db)
) -> dict[str, object]:
    try:
        qualification = create_candidate_precheck(db, candidate_id)
    except LeadCandidateNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return {
        "candidate_id": candidate_id,
        "qualification_id": qualification.id,
        "status": qualification.status.value,
        "is_microenterprise": qualification.is_microenterprise,
        "confidence_score": qualification.confidence_score,
    }


@router.get("/candidates/{candidate_id}/qualification")
def read_candidate_qualification(
    candidate_id: str, db: Session = Depends(get_db)
) -> dict[str, object]:
    try:
        qualification = get_latest_candidate_qualification(db, candidate_id)
    except LeadCandidateNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    if qualification is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Company qualification not found for candidate: {candidate_id}",
        )
    return _serialize_qualification(qualification)


@router.post("/candidates/{candidate_id}/promotion/evaluate")
def evaluate_candidate_promotion(
    candidate_id: str, db: Session = Depends(get_db)
) -> dict[str, object]:
    try:
        decision = evaluate_candidate_for_promotion(db, candidate_id)
    except LeadCandidateNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return {
        "candidate_id": candidate_id,
        "promotion_decision_id": decision.id,
        "status": decision.status.value,
        "reason_code": decision.reason_code,
        "confidence_score": decision.confidence_score,
    }


@router.get("/candidates/{candidate_id}/promotion")
def read_candidate_promotion(
    candidate_id: str, db: Session = Depends(get_db)
) -> dict[str, object]:
    try:
        decision = get_latest_promotion_decision(db, candidate_id)
    except LeadCandidateNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    if decision is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Promotion decision not found for candidate: {candidate_id}",
        )
    return _serialize_promotion_decision(decision)


@router.post("/candidates/{candidate_id}/website-probe/mock")
def run_candidate_website_probe(
    candidate_id: str, db: Session = Depends(get_db)
) -> dict[str, object]:
    try:
        probe = run_mock_website_probe(db, candidate_id)
    except LeadCandidateNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return {
        "candidate_id": candidate_id,
        "website_probe_id": probe.id,
        "status": probe.status.value,
        "confidence_score": probe.confidence_score,
    }


@router.post("/candidates/{candidate_id}/website-probe/live")
def run_candidate_live_website_probe(
    candidate_id: str, db: Session = Depends(get_db)
) -> dict[str, object]:
    try:
        probe = run_live_website_probe(db, candidate_id)
    except LeadCandidateNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except LiveWebsiteProbeDisabledError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    return {
        "candidate_id": candidate_id,
        "website_probe_id": probe.id,
        "status": probe.status.value,
        "confidence_score": probe.confidence_score,
    }


@router.get("/candidates/{candidate_id}/website-probe")
def read_candidate_website_probe(
    candidate_id: str, db: Session = Depends(get_db)
) -> dict[str, object]:
    try:
        probe = get_latest_website_probe(db, candidate_id)
    except LeadCandidateNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    if probe is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Website probe not found for candidate: {candidate_id}",
        )
    return _serialize_website_probe(probe)


@router.post("/candidates/{candidate_id}/scan-readiness/evaluate")
def evaluate_candidate_scan_readiness(
    candidate_id: str, db: Session = Depends(get_db)
) -> dict[str, object]:
    try:
        decision = evaluate_candidate_for_scan_readiness(db, candidate_id)
    except LeadCandidateNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return {
        "candidate_id": candidate_id,
        "scan_readiness_decision_id": decision.id,
        "status": decision.status.value,
        "reason_code": decision.reason_code,
        "confidence_score": decision.confidence_score,
    }


@router.get("/candidates/{candidate_id}/scan-readiness")
def read_candidate_scan_readiness(
    candidate_id: str, db: Session = Depends(get_db)
) -> dict[str, object]:
    try:
        decision = get_latest_scan_readiness_decision(db, candidate_id)
    except LeadCandidateNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    if decision is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scan readiness decision not found for candidate: {candidate_id}",
        )
    return _serialize_scan_readiness_decision(decision)


@router.post("/candidates/{candidate_id}/scans", status_code=status.HTTP_201_CREATED)
def create_candidate_scan_skeleton(
    candidate_id: str, db: Session = Depends(get_db)
) -> dict[str, object]:
    try:
        scan = create_scan_skeleton_for_candidate(db, candidate_id)
    except LeadCandidateNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ScanReadinessNotReadyError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return _serialize_scan_skeleton(scan)
