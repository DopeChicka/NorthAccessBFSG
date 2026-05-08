import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models import DiscoveryRun, LeadCandidate  # noqa: F401
from app.services.discovery_service import create_discovery_run


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


def test_discovery_run_can_be_created_in_db(db_session: Session) -> None:
    discovery_run = create_discovery_run(db_session, "Lübeck")

    assert discovery_run.id
    assert discovery_run.status.value == "done"
    assert discovery_run.city == "Lübeck"
    assert discovery_run.normalized_city == "luebeck"
    assert discovery_run.postal_codes
    assert discovery_run.keyword_groups
    assert discovery_run.query_plan
    assert discovery_run.error_message is None

    stored = db_session.get(DiscoveryRun, discovery_run.id)
    assert stored is not None
    assert stored.query_plan == discovery_run.query_plan
