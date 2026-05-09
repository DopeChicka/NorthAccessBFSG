from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import scans as scans_api
from app.api.scans import router as scans_router
from app.db.base import Base
from app.db.session import get_db
from app.models import EvidenceBundle, Finding, Lead, Scan, ScanEvidence, ScanStatus  # noqa: F401


def _make_client(db_session: Session) -> TestClient:
    app = FastAPI()
    app.include_router(scans_router)
    app.dependency_overrides[get_db] = lambda: db_session
    return TestClient(app)


def test_browser_smoke_endpoint_returns_evidence(monkeypatch) -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    db_session = TestingSessionLocal()
    try:
        lead = Lead(domain="example.com", company_name="Example GmbH")
        db_session.add(lead)
        db_session.flush()
        scan = Scan(lead_id=lead.id, status=ScanStatus.pending)
        db_session.add(scan)
        db_session.commit()
        db_session.refresh(scan)
        evidence = ScanEvidence(
            scan_id=scan.id,
            evidence_type="browser_smoke",
            path_or_key=f"scan-evidence/{scan.id}/browser-smoke.json",
            evidence_metadata={
                "final_url": "https://example.com",
                "page_title": "Smoke Page",
                "http_status": 200,
                "no_legal_conclusion": True,
            },
            hash=None,
        )
        db_session.add(evidence)
        db_session.commit()
        db_session.refresh(evidence)

        def fake_run_browser_smoke_probe(db: Session, scan_id: str) -> ScanEvidence:
            assert scan_id == scan.id
            return evidence

        monkeypatch.setattr(
            scans_api,
            "run_browser_smoke_probe",
            fake_run_browser_smoke_probe,
        )
        client = _make_client(db_session)

        response = client.post(f"/scans/{scan.id}/browser-smoke")

        assert response.status_code == 200
        payload = response.json()
        assert payload["scan_id"] == scan.id
        assert payload["evidence_id"] == evidence.id
        assert payload["evidence_type"] == "browser_smoke"
        assert payload["metadata"]["no_legal_conclusion"] is True
    finally:
        db_session.close()
        Base.metadata.drop_all(bind=engine)


def test_axe_homepage_endpoint_returns_evidence(monkeypatch) -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    db_session = TestingSessionLocal()
    try:
        lead = Lead(domain="example.com", company_name="Example GmbH")
        db_session.add(lead)
        db_session.flush()
        scan = Scan(lead_id=lead.id, status=ScanStatus.pending)
        db_session.add(scan)
        db_session.commit()
        db_session.refresh(scan)
        evidence = ScanEvidence(
            scan_id=scan.id,
            evidence_type="axe_homepage",
            path_or_key=f"scan-evidence/{scan.id}/axe-homepage.json",
            evidence_metadata={
                "final_url": "https://example.com",
                "page_title": "Axe Page",
                "http_status": 200,
                "findings_count": 0,
                "no_legal_conclusion": True,
            },
            hash=None,
        )
        db_session.add(evidence)
        db_session.commit()
        db_session.refresh(evidence)

        def fake_run_axe_homepage_audit(db: Session, scan_id: str) -> ScanEvidence:
            assert scan_id == scan.id
            return evidence

        monkeypatch.setattr(
            scans_api,
            "run_axe_homepage_audit",
            fake_run_axe_homepage_audit,
        )
        client = _make_client(db_session)

        response = client.post(f"/scans/{scan.id}/axe-homepage")

        assert response.status_code == 200
        payload = response.json()
        assert payload["scan_id"] == scan.id
        assert payload["evidence_id"] == evidence.id
        assert payload["evidence_type"] == "axe_homepage"
        assert payload["metadata"]["no_legal_conclusion"] is True
    finally:
        db_session.close()
        Base.metadata.drop_all(bind=engine)


def test_scan_evidence_quality_endpoint_returns_summary(monkeypatch) -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    db_session = TestingSessionLocal()
    try:
        lead = Lead(domain="example.com", company_name="Example GmbH")
        db_session.add(lead)
        db_session.flush()
        scan = Scan(lead_id=lead.id, status=ScanStatus.pending)
        db_session.add(scan)
        db_session.commit()
        db_session.refresh(scan)

        def fake_assess_scan_evidence_quality(
            db: Session, scan_id: str
        ) -> dict[str, object]:
            assert scan_id == scan.id
            return {
                "scan_id": scan.id,
                "evidence_count": 1,
                "missing_hash_count": 1,
                "missing_related_entity_count": 0,
                "has_journey_evidence": False,
                "has_axe_evidence": True,
                "has_browser_smoke_evidence": False,
                "quality_status": "usable",
                "reasons": ["includes_axe_evidence"],
                "no_legal_conclusion": True,
            }

        monkeypatch.setattr(
            scans_api,
            "assess_scan_evidence_quality",
            fake_assess_scan_evidence_quality,
        )
        client = _make_client(db_session)

        response = client.get(f"/scans/{scan.id}/evidence/quality")

        assert response.status_code == 200
        payload = response.json()
        assert payload["scan_id"] == scan.id
        assert payload["quality_status"] == "usable"
        assert payload["no_legal_conclusion"] is True
    finally:
        db_session.close()
        Base.metadata.drop_all(bind=engine)


def test_scan_review_summary_endpoint_returns_summary(monkeypatch) -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    db_session = TestingSessionLocal()
    try:
        lead = Lead(domain="example.com", company_name="Example GmbH")
        db_session.add(lead)
        db_session.flush()
        scan = Scan(lead_id=lead.id, status=ScanStatus.pending)
        db_session.add(scan)
        db_session.commit()
        db_session.refresh(scan)

        def fake_summarize_scan_review_status(
            db: Session, scan_id: str
        ) -> dict[str, object]:
            assert scan_id == scan.id
            return {
                "pending_count": 1,
                "approved_count": 0,
                "rejected_count": 0,
                "needs_more_info_count": 0,
                "total_review_items": 1,
                "has_blocking_reviews": True,
                "no_legal_conclusion": True,
            }

        monkeypatch.setattr(
            scans_api,
            "summarize_scan_review_status",
            fake_summarize_scan_review_status,
        )
        client = _make_client(db_session)

        response = client.get(f"/scans/{scan.id}/review/summary")

        assert response.status_code == 200
        payload = response.json()
        assert payload["pending_count"] == 1
        assert payload["has_blocking_reviews"] is True
        assert payload["no_legal_conclusion"] is True
    finally:
        db_session.close()
        Base.metadata.drop_all(bind=engine)
