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
from app.services.browser_smoke_service import (
    BrowserSmokeProbeError,
    BrowserSmokeResult,
    ScanNotFoundError,
    run_browser_smoke_probe,
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


def _fake_runner(url: str) -> BrowserSmokeResult:
    return BrowserSmokeResult(
        target_url=url,
        final_url=f"{url}/final",
        page_title="Smoke Page",
        http_status=200,
        captured_at=datetime.now(UTC).isoformat(),
    )


def test_unknown_scan_fails_clearly(db_session: Session) -> None:
    with pytest.raises(ScanNotFoundError, match="Scan not found: missing"):
        run_browser_smoke_probe(db_session, "missing", runner=_fake_runner)


def test_scan_without_url_fails_clearly(db_session: Session) -> None:
    scan = _create_scan(db_session, domain="")

    with pytest.raises(BrowserSmokeProbeError, match="no URL or domain"):
        run_browser_smoke_probe(db_session, scan.id, runner=_fake_runner)

    db_session.refresh(scan)
    assert scan.status.value == "failed"
    assert scan.error_message == "Scan has no URL or domain for browser smoke probe"


def test_browser_smoke_success_updates_scan_and_creates_evidence(
    db_session: Session,
) -> None:
    scan = _create_scan(db_session, domain="example.com")

    evidence = run_browser_smoke_probe(db_session, scan.id, runner=_fake_runner)

    db_session.refresh(scan)
    assert scan.status.value == "done"
    assert scan.completed_at is not None
    assert evidence.scan_id == scan.id
    assert evidence.evidence_type == "browser_smoke"
    assert evidence.path_or_key == f"scan-evidence/{scan.id}/browser-smoke.json"
    assert evidence.hash is None
    assert evidence.evidence_metadata["target_url"] == "https://example.com"
    assert evidence.evidence_metadata["final_url"] == "https://example.com/final"
    assert evidence.evidence_metadata["page_title"] == "Smoke Page"
    assert evidence.evidence_metadata["http_status"] == 200
    assert evidence.evidence_metadata["lead_candidate_id"] == "candidate-1"
    assert evidence.evidence_metadata["no_legal_conclusion"] is True
    assert scan.evidence_metadata["browser_smoke"]["evidence_id"] == evidence.id


def test_browser_smoke_makes_no_external_network_calls(
    monkeypatch,
    db_session: Session,
) -> None:
    def fail_network(*args, **kwargs):
        raise AssertionError("network access is not allowed in browser smoke tests")

    monkeypatch.setattr(socket, "create_connection", fail_network)
    scan = _create_scan(db_session, domain="example.com")

    evidence = run_browser_smoke_probe(db_session, scan.id, runner=_fake_runner)

    assert evidence.evidence_metadata["http_status"] == 200


def test_browser_smoke_evidence_has_no_forbidden_legal_claims(
    db_session: Session,
) -> None:
    scan = _create_scan(db_session, domain="example.com")

    evidence = run_browser_smoke_probe(db_session, scan.id, runner=_fake_runner)
    text = json.dumps(evidence.evidence_metadata, sort_keys=True).casefold()

    assert "legally obligated" not in text
    assert "violation" not in text
    assert "violates" not in text
    assert evidence.evidence_metadata["no_legal_conclusion"] is True
