import json
import socket

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models import (  # noqa: F401
    ComplianceMapping,
    EvidenceBundle,
    Finding,
    Journey,
    JourneyStatus,
    JourneyType,
    Lead,
    Report,
    ReportStatus,
    ReviewItem,
    ReviewItemStatus,
    ReviewPriority,
    ReviewSubjectType,
    Scan,
    ScanEvidence,
    ScanStatus,
)
from app.services.evidence_manifest_service import build_evidence_manifest
from app.services.report_service import (
    ScanNotFoundError,
    generate_scan_json_report,
    list_reports_for_scan,
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
        evidence_metadata={
            "lead_candidate_id": "candidate-1",
            "no_legal_conclusion": True,
        },
    )
    db_session.add(scan)
    db_session.flush()
    evidence = ScanEvidence(
        scan_id=scan.id,
        evidence_type="axe_homepage",
        path_or_key=f"scan-evidence/{scan.id}/axe-homepage.json",
        evidence_metadata={
            "target_url": "https://example.com",
            "findings_count": 1,
            "no_legal_conclusion": True,
        },
        hash=None,
    )
    db_session.add(evidence)
    db_session.flush()
    finding = Finding(
        scan_id=scan.id,
        rule_id="color-contrast",
        severity="high",
        description="Elements must meet contrast requirements",
        wcag_refs=["wcag143"],
        evidence={"scan_evidence_id": evidence.id, "no_legal_conclusion": True},
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
        confidence_score=0.9,
        evidence={"source": "test", "no_legal_conclusion": True},
    )
    db_session.add(mapping)
    db_session.flush()
    review_item = ReviewItem(
        subject_type=ReviewSubjectType.compliance_mapping,
        subject_id=mapping.id,
        status=ReviewItemStatus.pending,
        reason_code="compliance_mapping_review_required",
        priority=ReviewPriority.medium,
        evidence={"source": "test", "no_legal_conclusion": True},
    )
    db_session.add(review_item)
    journey = Journey(
        scan_id=scan.id,
        journey_type=JourneyType.homepage,
        status=JourneyStatus.ready,
        start_url="https://example.com",
        detected_url="https://example.com",
        signals={"no_legal_conclusion": True},
        evidence={"source": "test", "no_legal_conclusion": True},
    )
    db_session.add(journey)
    db_session.commit()
    db_session.refresh(scan)
    db_session.refresh(finding)
    db_session.refresh(mapping)
    return scan, finding, mapping


def test_evidence_manifest_collects_scan_evidence(db_session: Session) -> None:
    scan, _, _ = _create_scan_fixture(db_session)

    manifest = build_evidence_manifest(db_session, scan.id)

    assert manifest["scan_id"] == scan.id
    assert manifest["evidence_count"] == 1
    assert manifest["missing_hash_count"] == 1
    assert manifest["items"][0]["evidence_type"] == "axe_homepage"
    assert manifest["items"][0]["scan_id"] == scan.id
    assert manifest["items"][0]["related_entity_type"] is None
    assert manifest["items"][0]["related_entity_id"] is None
    assert manifest["items"][0]["storage_key"].endswith("axe-homepage.json")
    assert manifest["items"][0]["path_or_key"].endswith("axe-homepage.json")
    assert manifest["items"][0]["hash"] is None
    assert manifest["no_legal_conclusion"] is True


def test_generate_json_report_for_scan_with_findings(db_session: Session) -> None:
    scan, finding, _ = _create_scan_fixture(db_session)

    report = generate_scan_json_report(db_session, scan.id)

    assert report.status == ReportStatus.generated
    assert report.report_type.value == "json"
    assert report.generated_at is not None
    assert report.summary["finding_count"] == 1
    assert report.output["scan"]["id"] == scan.id
    assert report.output["findings"][0]["id"] == finding.id
    assert report.output["no_legal_conclusion"] is True


def test_report_includes_compliance_mappings_and_review_items(
    db_session: Session,
) -> None:
    scan, _, mapping = _create_scan_fixture(db_session)

    report = generate_scan_json_report(db_session, scan.id)

    assert report.output["compliance_mappings"][0]["id"] == mapping.id
    assert report.output["compliance_mappings"][0]["reference_signal_only"] is True
    assert len(report.output["review_items"]) == 1
    assert report.output["review_items"][0]["human_workflow_only"] is True


def test_report_includes_journeys(db_session: Session) -> None:
    scan, _, _ = _create_scan_fixture(db_session)

    report = generate_scan_json_report(db_session, scan.id)

    assert len(report.output["journeys"]) == 1
    assert report.output["journeys"][0]["journey_type"] == "homepage"
    assert report.output["journeys"][0]["planned_signal_only"] is True


def test_report_summary_counts_are_correct(db_session: Session) -> None:
    scan, _, _ = _create_scan_fixture(db_session)

    report = generate_scan_json_report(db_session, scan.id)

    assert report.summary == {
        "finding_count": 1,
        "compliance_mapping_count": 1,
        "review_item_count": 1,
        "evidence_count": 1,
        "critical_count": 0,
        "high_count": 1,
        "medium_count": 0,
        "low_count": 0,
        "no_legal_conclusion": True,
    }


def test_list_reports_for_scan(db_session: Session) -> None:
    scan, _, _ = _create_scan_fixture(db_session)
    report = generate_scan_json_report(db_session, scan.id)

    reports = list_reports_for_scan(db_session, scan.id)

    assert [item.id for item in reports] == [report.id]


def test_unknown_scan_fails_clearly(db_session: Session) -> None:
    with pytest.raises(ScanNotFoundError, match="Scan not found: missing"):
        generate_scan_json_report(db_session, "missing")

    with pytest.raises(ScanNotFoundError, match="Scan not found: missing"):
        list_reports_for_scan(db_session, "missing")


def test_report_generation_makes_no_external_calls(
    monkeypatch,
    db_session: Session,
) -> None:
    def fail_network(*args, **kwargs):
        raise AssertionError("network access is not allowed in report tests")

    monkeypatch.setattr(socket, "create_connection", fail_network)
    scan, _, _ = _create_scan_fixture(db_session)

    report = generate_scan_json_report(db_session, scan.id)

    assert report.summary["evidence_count"] == 1


def test_report_has_no_forbidden_legal_claims(db_session: Session) -> None:
    scan, _, _ = _create_scan_fixture(db_session)

    report = generate_scan_json_report(db_session, scan.id)
    text = json.dumps(
        {
            "summary": report.summary,
            "output": report.output,
            "evidence_manifest": report.evidence_manifest,
        },
        sort_keys=True,
    ).casefold()

    assert "legally_obligated" not in text
    assert "legally obligated" not in text
    assert "violation" not in text
    assert "illegal" not in text
    assert "guilty" not in text
    assert "certified" not in text
    assert "compliant" not in text
    assert "noncompliant" not in text
    assert report.output["no_legal_conclusion"] is True
