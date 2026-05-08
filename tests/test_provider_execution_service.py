import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models import DiscoveryRun, LeadCandidate  # noqa: F401
from app.services.discovery_service import DiscoveryRunNotFoundError, create_discovery_run
from app.services.provider_execution_service import execute_mock_provider


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


def test_provider_execution_persists_lead_candidates(db_session: Session) -> None:
    discovery_run = create_discovery_run(db_session, "Lübeck")

    summary = execute_mock_provider(db_session, discovery_run.id)

    assert summary.discovery_run_id == discovery_run.id
    assert summary.provider == "mock"
    assert summary.candidates_created == 10
    assert summary.candidates_total == 10

    candidates = db_session.query(LeadCandidate).all()
    assert len(candidates) == 10
    assert candidates[0].source == "mock"
    assert candidates[0].company_name.startswith("Mock Candidate Lübeck")
    assert candidates[0].raw_data["mock"] is True


def test_duplicate_provider_execution_does_not_duplicate_candidates(db_session: Session) -> None:
    discovery_run = create_discovery_run(db_session, "Lübeck")

    first = execute_mock_provider(db_session, discovery_run.id)
    second = execute_mock_provider(db_session, discovery_run.id)

    assert first.candidates_created == 10
    assert first.candidates_total == 10
    assert second.candidates_created == 0
    assert second.candidates_total == 10
    assert db_session.query(LeadCandidate).count() == 10


def test_provider_execution_unknown_run_fails_clearly(db_session: Session) -> None:
    with pytest.raises(DiscoveryRunNotFoundError, match="Discovery run not found: missing"):
        execute_mock_provider(db_session, "missing")
