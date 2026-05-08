from sqlalchemy import text

from app.db.base import Base
from app.db.session import engine
from app.models import Finding, Lead, Scan  # noqa: F401


_SCAN_SCHEMA_UPDATES = (
    "ALTER TYPE scan_status ADD VALUE IF NOT EXISTS 'failed'",
    "ALTER TABLE scans ADD COLUMN IF NOT EXISTS started_at TIMESTAMP WITH TIME ZONE",
    "ALTER TABLE scans ADD COLUMN IF NOT EXISTS completed_at TIMESTAMP WITH TIME ZONE",
    "ALTER TABLE scans ADD COLUMN IF NOT EXISTS failed_at TIMESTAMP WITH TIME ZONE",
)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    _ensure_scan_lifecycle_schema()


def _ensure_scan_lifecycle_schema() -> None:
    if engine.dialect.name != "postgresql":
        return

    with engine.begin() as connection:
        for statement in _SCAN_SCHEMA_UPDATES:
            connection.execute(text(statement))
