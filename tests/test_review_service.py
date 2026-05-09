import json
import socket

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models import (  # noqa: F401
    ComplianceMapping,
    DiscoveryRun,
    DiscoveryRunStatus,
    EvidenceBundle,
    Finding,
    Lead,
    LeadCandidate,
    ReviewItem,
    ReviewItemStatus,
    ReviewPriority,
    ReviewSubjectType,
    Scan,
    ScanEvidence,
    ScanStatus,
    WebsiteProbe,
    WebsiteProbeStatus,
)
from app.services.compliance_mapping_service import map_finding_compliance
from app.services.review_service import (
    auto_create_review_item_for_finding,
    auto_create_review_item_for_website_probe,
    create_review_for_compliance_mapping_if_required,
    create_review_for_finding_if_required,
    create_review_for_website_probe_if_required,
    create_review_item,
    get_review_item,
    list_review_items,
    ReviewItemValidationError,
    update_review_item_status,
)


@pytest.fixture()
def db_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    TestingSessionLocal = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)

    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


def _create_finding(db_session: Session, *, rule_id: str = "color-contrast") -> Finding:
    lead = Lead(domain="example.com", company_name="Example GmbH")
    db_session.add(lead)
    db_session.flush()
    scan = Scan(lead_id=lead.id, status=ScanStatus.done)
    db_session.add(scan)
    db_session.flush()
    finding = Finding(
        scan_id=scan.id,
        rule_id=rule_id,
        severity="high",
        description="Technical signal for review",
        wcag_refs=[],
        confidence_score=0.9,
        review_status="pending",
        evidence={"no_legal_conclusion": True},
    )
    db_session.add(finding)
    db_session.commit()
    db_session.refresh(finding)
    return finding


def test_create_review_item(db_session: Session) -> None:
    item = create_review_item(
        db_session,
        subject_type=ReviewSubjectType.finding,
        subject_id="finding-1",
        reason_code="manual_review",
        priority=ReviewPriority.high,
        notes="Needs human review",
        evidence={"source": "test"},
    )

    assert item.subject_type == ReviewSubjectType.finding
    assert item.subject_id == "finding-1"
    assert item.status == ReviewItemStatus.pending
    assert item.priority == ReviewPriority.high
    assert item.evidence["no_legal_conclusion"] is True


def test_get_review_item(db_session: Session) -> None:
    item = create_review_item(
        db_session,
        subject_type="finding",
        subject_id="finding-1",
        reason_code="manual_review",
    )

    fetched = get_review_item(db_session, item.id)

    assert fetched.id == item.id


def test_list_pending_review_items(db_session: Session) -> None:
    create_review_item(
        db_session,
        subject_type="finding",
        subject_id="finding-1",
        reason_code="manual_review",
        priority="medium",
    )
    create_review_item(
        db_session,
        subject_type="website_probe",
        subject_id="probe-1",
        reason_code="probe_review",
        priority="medium",
    )
    website_item = list_review_items(db_session, subject_type="website_probe")[0]
    update_review_item_status(db_session, website_item.id, status="approved")

    pending_items = list_review_items(db_session, status="pending")

    assert len(pending_items) == 1
    assert pending_items[0].subject_id == "finding-1"


def test_list_review_items_by_subject_type(db_session: Session) -> None:
    create_review_item(
        db_session,
        subject_type="finding",
        subject_id="finding-1",
        reason_code="manual_review",
    )
    create_review_item(
        db_session,
        subject_type="website_probe",
        subject_id="probe-1",
        reason_code="probe_review",
    )

    finding_items = list_review_items(db_session, subject_type="finding")

    assert len(finding_items) == 1
    assert finding_items[0].subject_type == ReviewSubjectType.finding


def test_update_review_item_status(db_session: Session) -> None:
    item = create_review_item(
        db_session,
        subject_type="finding",
        subject_id="finding-1",
        reason_code="manual_review",
    )

    updated = update_review_item_status(
        db_session,
        item.id,
        status="needs_more_info",
        reviewer="reviewer@example.com",
        notes="More context requested",
    )

    assert updated.status == ReviewItemStatus.needs_more_info
    assert updated.notes == "More context requested"
    assert updated.reviewer == "reviewer@example.com"
    assert updated.reviewed_at is not None
    assert updated.evidence["no_legal_conclusion"] is True


@pytest.mark.parametrize("status", ["approved", "rejected", "needs_more_info"])
def test_reviewed_at_is_set_after_terminal_review_status(
    db_session: Session, status: str
) -> None:
    item = create_review_item(
        db_session,
        subject_type="finding",
        subject_id=f"finding-{status}",
        reason_code="manual_review",
    )

    updated = update_review_item_status(db_session, item.id, status=status)

    assert updated.reviewed_at is not None


def test_invalid_values_fail_clearly(db_session: Session) -> None:
    with pytest.raises(ReviewItemValidationError, match="Invalid subject_type"):
        create_review_item(
            db_session,
            subject_type="invalid",
            subject_id="finding-1",
            reason_code="manual_review",
        )

    with pytest.raises(ReviewItemValidationError, match="Invalid priority"):
        create_review_item(
            db_session,
            subject_type="finding",
            subject_id="finding-1",
            reason_code="manual_review",
            priority="invalid",
        )

    item = create_review_item(
        db_session,
        subject_type="finding",
        subject_id="finding-1",
        reason_code="manual_review",
    )
    with pytest.raises(ReviewItemValidationError, match="Invalid status"):
        update_review_item_status(db_session, item.id, status="invalid")


def test_auto_create_from_compliance_mapping_review_required(db_session: Session) -> None:
    finding = _create_finding(db_session)

    mapping = map_finding_compliance(db_session, finding.id)
    review_items = list_review_items(
        db_session,
        status="pending",
        subject_type="compliance_mapping",
    )

    assert mapping.review_required is True
    assert len(review_items) == 1
    assert review_items[0].subject_id == mapping.id
    assert review_items[0].reason_code == "compliance_mapping_review_required"
    assert review_items[0].evidence["finding_id"] == finding.id


def test_duplicate_auto_create_returns_existing_pending_review_item(
    db_session: Session,
) -> None:
    finding = _create_finding(db_session)
    mapping = map_finding_compliance(db_session, finding.id)

    first = create_review_for_compliance_mapping_if_required(db_session, mapping.id)
    second = create_review_for_compliance_mapping_if_required(db_session, mapping.id)

    assert first is not None
    assert second is not None
    assert first.id == second.id
    assert (
        len(
            list_review_items(
                db_session,
                status="pending",
                subject_type="compliance_mapping",
            )
        )
        == 1
    )


def test_auto_create_from_pending_high_finding(db_session: Session) -> None:
    finding = _create_finding(db_session)

    item = create_review_for_finding_if_required(db_session, finding.id)

    assert item is not None
    assert item.subject_type == ReviewSubjectType.finding
    assert item.subject_id == finding.id
    assert item.priority == ReviewPriority.high
    assert item.reason_code == "high_severity_finding_review"


def test_auto_create_from_pending_critical_finding(db_session: Session) -> None:
    finding = _create_finding(db_session)
    finding.severity = "critical"
    db_session.commit()

    item = auto_create_review_item_for_finding(db_session, finding, commit=True)

    assert item is not None
    assert item.priority == ReviewPriority.critical


def test_auto_create_from_website_probe_needs_review(db_session: Session) -> None:
    discovery_run = DiscoveryRun(
        city="Berlin",
        normalized_city="berlin",
        status=DiscoveryRunStatus.done,
        keyword_groups=[],
        postal_codes=[],
        query_plan=[],
    )
    db_session.add(discovery_run)
    db_session.flush()
    candidate = LeadCandidate(
        discovery_run_id=discovery_run.id,
        source="test",
        company_name="Example GmbH",
        domain="example.com",
        raw_data={},
    )
    db_session.add(candidate)
    db_session.flush()
    probe = WebsiteProbe(
        lead_candidate_id=candidate.id,
        status=WebsiteProbeStatus.needs_review,
        normalized_domain="example.com",
        evidence={"no_legal_conclusion": True},
    )
    db_session.add(probe)
    db_session.commit()
    db_session.refresh(probe)

    item = create_review_for_website_probe_if_required(db_session, probe.id)

    assert item is not None
    assert item.subject_type == ReviewSubjectType.website_probe
    assert item.subject_id == probe.id
    assert item.reason_code == "website_probe_needs_review"


def test_review_service_makes_no_external_calls(
    monkeypatch,
    db_session: Session,
) -> None:
    def fail_network(*args, **kwargs):
        raise AssertionError("network access is not allowed in review tests")

    monkeypatch.setattr(socket, "create_connection", fail_network)

    item = create_review_item(
        db_session,
        subject_type="candidate",
        subject_id="candidate-1",
        reason_code="manual_review",
    )

    assert item.subject_id == "candidate-1"


def test_review_item_has_no_forbidden_legal_claims(db_session: Session) -> None:
    item = create_review_item(
        db_session,
        subject_type="finding",
        subject_id="finding-1",
        reason_code="manual_review",
        evidence={"source": "test"},
    )
    text = json.dumps(item.evidence, sort_keys=True).casefold()

    assert "legally obligated" not in text
    assert "violation" not in text
    assert "violates" not in text
    assert item.evidence["no_legal_conclusion"] is True
