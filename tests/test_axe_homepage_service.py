import json
import socket
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models import (  # noqa: F401
    EvidenceBundle,
    Finding,
    Lead,
    Scan,
    ScanEvidence,
    ScanStatus,
)
from app.services.axe_homepage_service import (
    AxeHomepageAuditError,
    AxeHomepageResult,
    AxeViolation,
    ScanNotFoundError,
    run_axe_homepage_audit,
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


def _create_scan(db_session: Session, *, domain: str = "example.com") -> Scan:
    lead = Lead(domain=domain, company_name="Example GmbH")
    db_session.add(lead)
    db_session.flush()
    scan = Scan(
        lead_id=lead.id,
        status=ScanStatus.pending,
        evidence_metadata={
            "lead_candidate_id": "candidate-1",
            "no_legal_conclusion": True,
        },
    )
    db_session.add(scan)
    db_session.commit()
    db_session.refresh(scan)
    return scan


def _fake_runner(url: str) -> AxeHomepageResult:
    return AxeHomepageResult(
        target_url=url,
        final_url=f"{url}/final",
        page_title="Axe Page",
        http_status=200,
        captured_at=datetime.now(UTC).isoformat(),
        violations=[
            AxeViolation(
                rule_id="color-contrast",
                impact="serious",
                description="Elements must meet contrast requirements",
                help_url="https://dequeuniversity.com/rules/axe/color-contrast",
                wcag_refs=["wcag143"],
                nodes=[{"target": [".button"]}],
            )
        ],
    )


def test_unknown_scan_fails_clearly(db_session: Session) -> None:
    with pytest.raises(ScanNotFoundError, match="Scan not found: missing"):
        run_axe_homepage_audit(db_session, "missing", runner=_fake_runner)


def test_scan_without_url_fails_clearly(db_session: Session) -> None:
    scan = _create_scan(db_session, domain="")

    with pytest.raises(AxeHomepageAuditError, match="no URL or domain"):
        run_axe_homepage_audit(db_session, scan.id, runner=_fake_runner)

    db_session.refresh(scan)
    assert scan.status.value == "failed"
    assert scan.error_message == "Scan has no URL or domain for axe homepage audit"


def test_successful_axe_homepage_creates_evidence_and_findings(
    db_session: Session,
) -> None:
    scan = _create_scan(db_session, domain="example.com")

    evidence = run_axe_homepage_audit(db_session, scan.id, runner=_fake_runner)
    findings = db_session.query(Finding).filter(Finding.scan_id == scan.id).all()

    db_session.refresh(scan)
    assert scan.status.value == "done"
    assert scan.completed_at is not None
    assert evidence.scan_id == scan.id
    assert evidence.evidence_type == "axe_homepage"
    assert evidence.path_or_key == f"scan-evidence/{scan.id}/axe-homepage.json"
    assert evidence.hash is None
    assert evidence.evidence_metadata["target_url"] == "https://example.com"
    assert evidence.evidence_metadata["final_url"] == "https://example.com/final"
    assert evidence.evidence_metadata["page_title"] == "Axe Page"
    assert evidence.evidence_metadata["http_status"] == 200
    assert evidence.evidence_metadata["findings_count"] == 1
    assert evidence.evidence_metadata["no_legal_conclusion"] is True
    assert scan.evidence_metadata["axe_homepage"]["evidence_id"] == evidence.id

    assert len(findings) == 1
    finding = findings[0]
    assert finding.rule_id == "color-contrast"
    assert finding.severity == "high"
    assert finding.description == "Elements must meet contrast requirements"
    assert finding.wcag_refs == ["wcag143"]
    assert finding.review_status == "pending"
    assert finding.confidence_score == 0.9
    assert finding.evidence["scan_evidence_id"] == evidence.id
    assert finding.evidence["sample_targets"] == [[".button"]]
    assert finding.evidence["no_legal_conclusion"] is True


def test_axe_homepage_makes_no_external_network_calls(
    monkeypatch,
    db_session: Session,
) -> None:
    def fail_network(*args, **kwargs):
        raise AssertionError("network access is not allowed in axe homepage tests")

    monkeypatch.setattr(socket, "create_connection", fail_network)
    scan = _create_scan(db_session, domain="example.com")

    evidence = run_axe_homepage_audit(db_session, scan.id, runner=_fake_runner)

    assert evidence.evidence_metadata["http_status"] == 200


def test_axe_homepage_has_no_forbidden_legal_claims(db_session: Session) -> None:
    scan = _create_scan(db_session, domain="example.com")

    evidence = run_axe_homepage_audit(db_session, scan.id, runner=_fake_runner)
    finding = db_session.query(Finding).filter(Finding.scan_id == scan.id).one()
    text = json.dumps(
        {
            "evidence": evidence.evidence_metadata,
            "finding_evidence": finding.evidence,
            "finding_metadata": finding.evidence_metadata,
        },
        sort_keys=True,
    ).casefold()

    assert "legally obligated" not in text
    assert "violation" not in text
    assert "violates" not in text
    assert evidence.evidence_metadata["no_legal_conclusion"] is True
    assert finding.evidence["no_legal_conclusion"] is True
