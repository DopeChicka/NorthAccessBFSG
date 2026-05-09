import json
import socket

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models import Lead, Scan, ScanEvidence, ScanStatus  # noqa: F401
from app.services.evidence_quality_service import (
    ScanNotFoundError,
    assess_scan_evidence_quality,
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


def test_evidence_quality_insufficient_with_no_evidence(db_session: Session) -> None:
    scan = _create_scan(db_session)

    quality = assess_scan_evidence_quality(db_session, scan.id)

    assert quality["quality_status"] == "insufficient"
    assert quality["evidence_count"] == 0
    assert quality["reasons"] == ["no_evidence_available"]
    assert quality["no_legal_conclusion"] is True


def test_evidence_quality_usable_with_axe_and_journey_evidence(
    db_session: Session,
) -> None:
    scan = _create_scan(db_session)
    db_session.add(
        ScanEvidence(
            scan_id=scan.id,
            evidence_type="axe_journey",
            related_entity_type="journey",
            related_entity_id="journey-1",
            path_or_key=f"scan-evidence/{scan.id}/journey-1/axe.json",
            evidence_metadata={"no_legal_conclusion": True},
            hash=None,
        )
    )
    db_session.add(
        ScanEvidence(
            scan_id=scan.id,
            evidence_type="browser_smoke",
            path_or_key=f"scan-evidence/{scan.id}/browser-smoke.json",
            evidence_metadata={"no_legal_conclusion": True},
            hash=None,
        )
    )
    db_session.commit()

    quality = assess_scan_evidence_quality(db_session, scan.id)

    assert quality["quality_status"] == "usable"
    assert quality["has_axe_evidence"] is True
    assert quality["has_journey_evidence"] is True
    assert quality["has_browser_smoke_evidence"] is True
    assert "includes_axe_evidence" in quality["reasons"]
    assert "includes_journey_evidence" in quality["reasons"]


def test_evidence_quality_unknown_scan_fails_clearly(db_session: Session) -> None:
    with pytest.raises(ScanNotFoundError, match="Scan not found: missing"):
        assess_scan_evidence_quality(db_session, "missing")


def test_evidence_quality_makes_no_external_calls(
    monkeypatch,
    db_session: Session,
) -> None:
    def fail_network(*args, **kwargs):
        raise AssertionError("network access is not allowed in evidence quality tests")

    monkeypatch.setattr(socket, "create_connection", fail_network)
    scan = _create_scan(db_session)

    quality = assess_scan_evidence_quality(db_session, scan.id)

    assert quality["quality_status"] == "insufficient"


def test_evidence_quality_has_no_forbidden_legal_claims(db_session: Session) -> None:
    scan = _create_scan(db_session)
    quality = assess_scan_evidence_quality(db_session, scan.id)
    text = json.dumps(quality, sort_keys=True).casefold()

    assert "legally_obligated" not in text
    assert "legally obligated" not in text
    assert "violation" not in text
    assert "illegal" not in text
    assert "guilty" not in text
    assert "certified" not in text
    assert "compliant" not in text
    assert "noncompliant" not in text
