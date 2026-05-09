import json
import socket
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models import (  # noqa: F401
    DeltaComparison,
    DeltaComparisonStatus,
    EvidenceBundle,
    Finding,
    Lead,
    Report,
    Scan,
    ScanEvidence,
    ScanStatus,
)
from app.services.delta_comparison_service import (
    BaselineScanNotFoundError,
    TargetScanNotFoundError,
    generate_delta_comparison,
    list_delta_comparisons_for_scan,
)
from app.services.finding_fingerprint_service import build_finding_fingerprint


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


def _create_finding(
    db_session: Session,
    scan: Scan,
    *,
    rule_id: str,
    severity: str = "high",
    description: str = "Elements must meet contrast requirements",
    target: str = ".button",
) -> Finding:
    finding = Finding(
        scan_id=scan.id,
        rule_id=rule_id,
        severity=severity,
        description=description,
        wcag_refs=[],
        evidence={
            "sample_targets": [[target]],
            "target_url": "https://example.com",
            "no_legal_conclusion": True,
        },
        confidence_score=0.9,
        review_status="pending",
    )
    db_session.add(finding)
    db_session.commit()
    db_session.refresh(finding)
    return finding


def test_fingerprint_is_deterministic(db_session: Session) -> None:
    scan = _create_scan(db_session)
    finding = _create_finding(db_session, scan, rule_id="color-contrast")

    assert build_finding_fingerprint(finding) == build_finding_fingerprint(finding)


def test_fingerprint_ignores_ids_and_timestamps(db_session: Session) -> None:
    first_scan = _create_scan(db_session)
    second_scan = _create_scan(db_session)
    first = _create_finding(db_session, first_scan, rule_id="image-alt", target="img.logo")
    second = _create_finding(db_session, second_scan, rule_id="image-alt", target="img.logo")
    first.created_at = datetime(2025, 1, 1, tzinfo=UTC)
    second.created_at = datetime(2026, 1, 1, tzinfo=UTC)

    assert first.id != second.id
    assert build_finding_fingerprint(first) == build_finding_fingerprint(second)


def test_generate_delta_with_new_resolved_and_unchanged_findings(
    db_session: Session,
) -> None:
    baseline = _create_scan(db_session)
    target = _create_scan(db_session)
    unchanged = _create_finding(
        db_session,
        baseline,
        rule_id="color-contrast",
        target=".shared",
    )
    _create_finding(db_session, target, rule_id="color-contrast", target=".shared")
    resolved = _create_finding(db_session, baseline, rule_id="image-alt", target="img.old")
    new = _create_finding(db_session, target, rule_id="label", target="#email")

    comparison = generate_delta_comparison(db_session, baseline.id, target.id)

    assert comparison.status == DeltaComparisonStatus.generated
    assert comparison.summary == {
        "baseline_finding_count": 2,
        "target_finding_count": 2,
        "new_count": 1,
        "resolved_count": 1,
        "unchanged_count": 1,
        "no_legal_conclusion": True,
    }
    assert comparison.output["new_findings"][0]["finding_id"] == new.id
    assert comparison.output["resolved_findings"][0]["finding_id"] == resolved.id
    assert (
        comparison.output["unchanged_findings"][0]["baseline"]["finding_id"]
        == unchanged.id
    )


def test_unknown_scans_fail_clearly(db_session: Session) -> None:
    target = _create_scan(db_session)
    baseline = _create_scan(db_session)

    with pytest.raises(BaselineScanNotFoundError, match="Baseline scan not found"):
        generate_delta_comparison(db_session, "missing", target.id)

    with pytest.raises(TargetScanNotFoundError, match="Target scan not found"):
        generate_delta_comparison(db_session, baseline.id, "missing")


def test_list_delta_comparisons_for_scan(db_session: Session) -> None:
    baseline = _create_scan(db_session)
    target = _create_scan(db_session)
    _create_finding(db_session, baseline, rule_id="color-contrast")
    _create_finding(db_session, target, rule_id="label")
    comparison = generate_delta_comparison(db_session, baseline.id, target.id)

    comparisons = list_delta_comparisons_for_scan(db_session, target.id)

    assert [item.id for item in comparisons] == [comparison.id]


def test_delta_comparison_makes_no_external_calls(
    monkeypatch,
    db_session: Session,
) -> None:
    def fail_network(*args, **kwargs):
        raise AssertionError("network access is not allowed in delta tests")

    monkeypatch.setattr(socket, "create_connection", fail_network)
    baseline = _create_scan(db_session)
    target = _create_scan(db_session)
    _create_finding(db_session, baseline, rule_id="color-contrast")

    comparison = generate_delta_comparison(db_session, baseline.id, target.id)

    assert comparison.summary["resolved_count"] == 1


def test_delta_output_has_no_forbidden_legal_claims(db_session: Session) -> None:
    baseline = _create_scan(db_session)
    target = _create_scan(db_session)
    _create_finding(db_session, baseline, rule_id="color-contrast")
    _create_finding(db_session, target, rule_id="label")

    comparison = generate_delta_comparison(db_session, baseline.id, target.id)
    text = json.dumps(
        {"summary": comparison.summary, "output": comparison.output},
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
    assert comparison.output["no_legal_conclusion"] is True
