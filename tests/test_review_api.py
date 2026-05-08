from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.review import router as review_router
from app.db.base import Base
from app.db.session import get_db
from app.models import ReviewItem  # noqa: F401


def _make_client(db_session: Session) -> TestClient:
    app = FastAPI()
    app.include_router(review_router)
    app.dependency_overrides[get_db] = lambda: db_session
    return TestClient(app)


def test_review_item_api_create_list_get_and_update() -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    db_session = TestingSessionLocal()
    try:
        client = _make_client(db_session)

        create_response = client.post(
            "/review/items",
            json={
                "subject_type": "finding",
                "subject_id": "finding-1",
                "reason_code": "manual_review",
                "priority": "high",
                "evidence": {"source": "api_test"},
            },
        )
        assert create_response.status_code == 200
        created = create_response.json()
        assert created["status"] == "pending"
        assert created["priority"] == "high"
        assert created["evidence"]["no_legal_conclusion"] is True

        list_response = client.get("/review/items?status=pending")
        assert list_response.status_code == 200
        assert len(list_response.json()) == 1

        get_response = client.get(f"/review/items/{created['id']}")
        assert get_response.status_code == 200
        assert get_response.json()["id"] == created["id"]

        update_response = client.patch(
            f"/review/items/{created['id']}",
            json={
                "status": "approved",
                "notes": "Reviewed as technical signal",
                "reviewer": "reviewer@example.com",
            },
        )
        assert update_response.status_code == 200
        updated = update_response.json()
        assert updated["status"] == "approved"
        assert updated["notes"] == "Reviewed as technical signal"
        assert updated["reviewer"] == "reviewer@example.com"
        assert updated["reviewed_at"] is not None
    finally:
        db_session.close()
        Base.metadata.drop_all(bind=engine)
