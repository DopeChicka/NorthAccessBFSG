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
    Lead,
    Scan,
    ScanEvidence,
    ScanStatus,
)
from app.services.compliance_mapping_service import (
    FindingNotFoundError,
    ScanNotFoundError,
    map_finding_compliance,
    map_scan_findings_compliance,
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


def _create_scan(db_session: Session) -> Scan:
    lead = Lead(domain="example.com", company_name="Example GmbH")
    db_session.add(lead)
    db_session.flush()
    scan = Scan(lead_id=lead.id, status=ScanStatus.done)
    db_session.add(scan)
    db_session.commit()
    db_session.refresh(scan)
    return scan


def _create_finding(db_session: Session, scan: Scan, *, rule_id: str) -> Finding:
    finding = Finding(
        scan_id=scan.id,
        rule_id=rule_id,
        severity="high",
        description="Technical signal for review",
        wcag_refs=[],
        confidence_score=0.9,
        evidence={"no_legal_conclusion": True},
    )
    db_session.add(finding)
    db_session.commit()
    db_session.refresh(finding)
    return finding


def test_known_axe_rule_maps_to_wcag_refs(db_session: Session) -> None:
    scan = _create_scan(db_session)
    finding = _create_finding(db_session, scan, rule_id="color-contrast")

    mapping = map_finding_compliance(db_session, finding.id)

    assert mapping.finding_id == finding.id
    assert mapping.source_rule_id == "color-contrast"
    assert mapping.wcag_refs == ["wcag143"]
    assert mapping.en_301_549_refs == ["EN 301 549 9.1.4.3"]
    assert mapping.bfsg_signal_refs == ["bfsg_visual_contrast_signal"]
    assert mapping.review_required is True
    assert mapping.confidence_score == 0.9
    assert mapping.evidence["no_legal_conclusion"] is True


def test_unknown_axe_rule_requires_review(db_session: Session) -> None:
    scan = _create_scan(db_session)
    finding = _create_finding(db_session, scan, rule_id="unknown-custom-rule")

    mapping = map_finding_compliance(db_session, finding.id)

    assert mapping.wcag_refs == []
    assert mapping.en_301_549_refs == []
    assert mapping.bfsg_signal_refs == []
    assert mapping.review_required is True
    assert mapping.confidence_score == 0.2
    assert mapping.evidence["mapping_confidence"] == 0.2


def test_scan_level_mapping_maps_all_findings(db_session: Session) -> None:
    scan = _create_scan(db_session)
    first = _create_finding(db_session, scan, rule_id="color-contrast")
    second = _create_finding(db_session, scan, rule_id="image-alt")

    mappings = map_scan_findings_compliance(db_session, scan.id)

    assert len(mappings) == 2
    assert {mapping.finding_id for mapping in mappings} == {first.id, second.id}
    assert db_session.query(ComplianceMapping).count() == 2


def test_mapping_fails_clearly_for_missing_records(db_session: Session) -> None:
    with pytest.raises(FindingNotFoundError, match="Finding not found: missing"):
        map_finding_compliance(db_session, "missing")

    with pytest.raises(ScanNotFoundError, match="Scan not found: missing"):
        map_scan_findings_compliance(db_session, "missing")


def test_compliance_mapping_makes_no_external_calls(
    monkeypatch,
    db_session: Session,
) -> None:
    def fail_network(*args, **kwargs):
        raise AssertionError("network access is not allowed in compliance mapping tests")

    monkeypatch.setattr(socket, "create_connection", fail_network)
    scan = _create_scan(db_session)
    finding = _create_finding(db_session, scan, rule_id="image-alt")

    mapping = map_finding_compliance(db_session, finding.id)

    assert mapping.wcag_refs == ["wcag111"]


def test_compliance_mapping_has_no_forbidden_legal_claims(db_session: Session) -> None:
    scan = _create_scan(db_session)
    finding = _create_finding(db_session, scan, rule_id="label")

    mapping = map_finding_compliance(db_session, finding.id)
    text = json.dumps(
        {
            "wcag_refs": mapping.wcag_refs,
            "en_301_549_refs": mapping.en_301_549_refs,
            "bfsg_signal_refs": mapping.bfsg_signal_refs,
            "evidence": mapping.evidence,
        },
        sort_keys=True,
    ).casefold()

    assert "legally obligated" not in text
    assert "violation" not in text
    assert "violates" not in text
    assert mapping.evidence["no_legal_conclusion"] is True
