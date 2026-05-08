from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.compliance_mapping import router as compliance_mapping_router
from app.db.base import Base
from app.db.session import get_db
from app.models import ComplianceMapping, Finding, Lead, Scan, ScanStatus  # noqa: F401


def _make_client(db_session: Session) -> TestClient:
    app = FastAPI()
    app.include_router(compliance_mapping_router)
    app.dependency_overrides[get_db] = lambda: db_session
    return TestClient(app)


def _create_scan_with_finding(db_session: Session, *, rule_id: str = "color-contrast"):
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
        evidence={"no_legal_conclusion": True},
    )
    db_session.add(finding)
    db_session.commit()
    db_session.refresh(scan)
    db_session.refresh(finding)
    return scan, finding


def test_finding_compliance_mapping_endpoints() -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    db_session = TestingSessionLocal()
    try:
        _, finding = _create_scan_with_finding(db_session)
        client = _make_client(db_session)

        post_response = client.post(f"/findings/{finding.id}/compliance/map")
        assert post_response.status_code == 200
        post_payload = post_response.json()
        assert post_payload["finding_id"] == finding.id
        assert post_payload["wcag_refs"] == ["wcag143"]
        assert post_payload["evidence"]["no_legal_conclusion"] is True

        get_response = client.get(f"/findings/{finding.id}/compliance")
        assert get_response.status_code == 200
        assert get_response.json()["id"] == post_payload["id"]
    finally:
        db_session.close()
        Base.metadata.drop_all(bind=engine)


def test_scan_compliance_mapping_endpoint_maps_all_findings() -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    db_session = TestingSessionLocal()
    try:
        scan, first = _create_scan_with_finding(db_session, rule_id="color-contrast")
        second = Finding(
            scan_id=scan.id,
            rule_id="unknown-custom-rule",
            severity="medium",
            description="Technical signal for review",
            wcag_refs=[],
            evidence={"no_legal_conclusion": True},
        )
        db_session.add(second)
        db_session.commit()
        db_session.refresh(second)
        client = _make_client(db_session)

        response = client.post(f"/scans/{scan.id}/compliance/map")

        assert response.status_code == 200
        payload = response.json()
        assert payload["scan_id"] == scan.id
        assert payload["mapped_count"] == 2
        assert {item["finding_id"] for item in payload["mappings"]} == {
            first.id,
            second.id,
        }
        unknown_mapping = [
            item
            for item in payload["mappings"]
            if item["source_rule_id"] == "unknown-custom-rule"
        ][0]
        assert unknown_mapping["review_required"] is True
        assert unknown_mapping["wcag_refs"] == []
    finally:
        db_session.close()
        Base.metadata.drop_all(bind=engine)
