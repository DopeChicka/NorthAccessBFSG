from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models import (  # noqa: F401
    DEFAULT_FINDING_LEGAL_DISCLAIMER,
    Finding,
    FindingCategory,
    FindingResponsibleRole,
    Lead,
    Scan,
    ScanStatus,
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


def test_finding_defaults_for_manual_review_and_disclaimer(db_session: Session) -> None:
    scan = _create_scan(db_session)
    finding = Finding(
        scan_id=scan.id,
        rule_id="color-contrast",
        severity="high",
        description="Contrast signal",
    )
    db_session.add(finding)
    db_session.commit()
    db_session.refresh(finding)

    assert finding.category == FindingCategory.accessibility
    assert finding.source_tool == "unknown"
    assert finding.manual_review_required is True
    assert finding.legal_disclaimer == DEFAULT_FINDING_LEGAL_DISCLAIMER
    assert finding.responsible_role == FindingResponsibleRole.developer
    assert finding.technical_evidence == {}


def test_finding_supports_required_categories_and_responsible_roles(
    db_session: Session,
) -> None:
    scan = _create_scan(db_session)
    supported_roles = [
        FindingResponsibleRole.developer,
        FindingResponsibleRole.content,
        FindingResponsibleRole.design,
        FindingResponsibleRole.ux,
        FindingResponsibleRole.auditor,
    ]
    supported_categories = [
        FindingCategory.accessibility,
        FindingCategory.technical,
        FindingCategory.privacy,
        FindingCategory.seo,
    ]

    for index, category in enumerate(supported_categories):
        finding = Finding(
            scan_id=scan.id,
            category=category,
            rule_id=f"rule-{index}",
            severity="info",
            title=f"Finding {index}",
            description="Signal",
            responsible_role=supported_roles[index % len(supported_roles)],
        )
        db_session.add(finding)

    db_session.commit()
    persisted = db_session.query(Finding).all()

    assert {item.category for item in persisted} == set(supported_categories)
    assert {item.responsible_role for item in persisted}.issubset(set(supported_roles))
