from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.discovery.place_resolver import PlaceDataError, PlaceNotFoundError, normalize_city_name
from app.discovery.query_planner import build_query_plan
from app.models.discovery_run import DiscoveryRun, DiscoveryRunStatus
from app.models.lead_candidate import LeadCandidate


class DiscoveryRunNotFoundError(LookupError):
    pass


def create_discovery_run(db: Session, city: str) -> DiscoveryRun:
    discovery_run = DiscoveryRun(
        city=city,
        normalized_city=normalize_city_name(city),
        status=DiscoveryRunStatus.pending,
        keyword_groups=[],
        postal_codes=[],
        query_plan=[],
    )
    db.add(discovery_run)
    db.flush()

    try:
        plan = build_query_plan(city)
    except (PlaceDataError, PlaceNotFoundError) as exc:
        discovery_run.status = DiscoveryRunStatus.failed
        discovery_run.completed_at = datetime.now(UTC)
        discovery_run.error_message = str(exc)
        db.commit()
        db.refresh(discovery_run)
        raise

    discovery_run.city = plan.city
    discovery_run.normalized_city = normalize_city_name(plan.city)
    discovery_run.status = DiscoveryRunStatus.done
    discovery_run.keyword_groups = plan.keyword_groups
    discovery_run.postal_codes = plan.postal_codes
    discovery_run.query_plan = plan.query_plan
    discovery_run.completed_at = datetime.now(UTC)
    discovery_run.error_message = None
    db.commit()
    db.refresh(discovery_run)
    return discovery_run


def get_discovery_run(db: Session, run_id: str) -> DiscoveryRun:
    discovery_run = db.get(DiscoveryRun, run_id)
    if discovery_run is None:
        raise DiscoveryRunNotFoundError(f"Discovery run not found: {run_id}")
    return discovery_run


def list_lead_candidates(db: Session, run_id: str) -> list[LeadCandidate]:
    get_discovery_run(db, run_id)
    return (
        db.query(LeadCandidate)
        .filter(LeadCandidate.discovery_run_id == run_id)
        .order_by(LeadCandidate.created_at.asc(), LeadCandidate.id.asc())
        .all()
    )
