import json
import socket

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models import (  # noqa: F401
    ComplianceMapping,
    Finding,
    Lead,
    ReviewItem,
    ReviewItemStatus,
    ReviewPriority,
    ReviewSubjectType,
    Scan,
    ScanStatus,
)
from app.services.review_finalization_service import (
    ScanNotFoundError,
    summarize_scan_review_status,
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


def _create_scan_fixture(db_session: Session) -> tuple[Scan, Finding, ComplianceMapping]:
    lead = Lead(domain="example.com", company_name="Example GmbH")
    db_session.add(lead)
    db_session.flush()
    scan = Scan(
        lead_id=lead.id,
        status=ScanStatus.done,
        evidence_metadata={"lead_candidate_id": "candidate-1"},
    )
    db_session.add(scan)
    db_session.flush()
    finding = Finding(
        scan_id=scan.id,
        rule_id="color-contrast",
        severity="high",
        description="Contrast signal",
        wcag_refs=["wcag143"],
        evidence={"no_legal_conclusion": True},
        confidence_score=0.9,
        review_status="pending",
    )
    db_session.add(finding)
    db_session.flush()
    mapping = ComplianceMapping(
        finding_id=finding.id,
        source_rule_id="color-contrast",
        wcag_refs=["wcag143"],
        en_301_549_refs=["EN 301 549 9.1.4.3"],
        bfsg_signal_refs=["bfsg_visual_contrast_signal"],
        review_required=True,
        confidence_score=0.8,
        evidence={"no_legal_conclusion": True},
    )
    db_session.add(mapping)
    db_session.flush()
    db_session.add_all(
        [
            ReviewItem(
                subject_type=ReviewSubjectType.finding,
                subject_id=finding.id,
                status=ReviewItemStatus.pending,
                reason_code="finding_pending_review",
                priority=ReviewPriority.high,
                evidence={"no_legal_conclusion": True},
            ),
            ReviewItem(
                subject_type=ReviewSubjectType.compliance_mapping,
                subject_id=mapping.id,
                status=ReviewItemStatus.approved,
                reason_code="mapping_reviewed",
                priority=ReviewPriority.medium,
                evidence={"no_legal_conclusion": True},
            ),
            ReviewItem(
                subject_type=ReviewSubjectType.candidate,
                subject_id="candidate-1",
                status=ReviewItemStatus.rejected,
                reason_code="candidate_rejected_for_signal_quality",
                priority=ReviewPriority.medium,
                evidence={"no_legal_conclusion": True},
            ),
            ReviewItem(
                subject_type=ReviewSubjectType.candidate,
                subject_id="candidate-1",
                status=ReviewItemStatus.needs_more_info,
                reason_code="candidate_needs_more_info",
                priority=ReviewPriority.low,
                evidence={"no_legal_conclusion": True},
            ),
        ]
    )
    db_session.commit()
    db_session.refresh(scan)
    db_session.refresh(finding)
    db_session.refresh(mapping)
    return scan, finding, mapping


def test_review_summary_counts_statuses_correctly(db_session: Session) -> None:
    scan, _, _ = _create_scan_fixture(db_session)

    summary = summarize_scan_review_status(db_session, scan.id)

    assert summary["pending_count"] == 1
    assert summary["approved_count"] == 1
    assert summary["rejected_count"] == 1
    assert summary["needs_more_info_count"] == 1
    assert summary["total_review_items"] == 4
    assert summary["has_blocking_reviews"] is True
    assert summary["no_legal_conclusion"] is True


def test_review_summary_unknown_scan_fails_clearly(db_session: Session) -> None:
    with pytest.raises(ScanNotFoundError, match="Scan not found: missing"):
        summarize_scan_review_status(db_session, "missing")


def test_review_summary_makes_no_external_calls(
    monkeypatch,
    db_session: Session,
) -> None:
    def fail_network(*args, **kwargs):
        raise AssertionError(
            "network access is not allowed in review finalization tests"
        )

    monkeypatch.setattr(socket, "create_connection", fail_network)
    scan, _, _ = _create_scan_fixture(db_session)

    summary = summarize_scan_review_status(db_session, scan.id)

    assert summary["total_review_items"] == 4


def test_review_summary_has_no_forbidden_legal_claims(db_session: Session) -> None:
    scan, _, _ = _create_scan_fixture(db_session)
    summary = summarize_scan_review_status(db_session, scan.id)
    text = json.dumps(summary, sort_keys=True).casefold()

    assert "legally_obligated" not in text
    assert "legally obligated" not in text
    assert "violation" not in text
    assert "illegal" not in text
    assert "guilty" not in text
    assert "certified" not in text
    assert "compliant" not in text
    assert "noncompliant" not in text
