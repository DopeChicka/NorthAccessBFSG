from sqlalchemy import text

from app.db.base import Base
from app.db.session import engine
from app.models import (  # noqa: F401
    CompanyEnrichment,
    CompanyQualification,
    ComplianceFinding,
    ComplianceMapping,
    DeltaComparison,
    DiscoveryRun,
    EvidenceBundle,
    Finding,
    Journey,
    Lead,
    LeadCandidate,
    PromotionDecision,
    Report,
    ReviewItem,
    Scan,
    ScanEvidence,
    ScanReadinessDecision,
    WebsiteProbe,
)

_SCAN_ENUM_UPDATES = (
    "ALTER TYPE scan_status ADD VALUE IF NOT EXISTS 'processing'",
    "ALTER TYPE scan_status ADD VALUE IF NOT EXISTS 'failed'",
)

_SCAN_COLUMN_UPDATES = (
    "ALTER TABLE scans ADD COLUMN IF NOT EXISTS started_at TIMESTAMP WITH TIME ZONE",
    "ALTER TABLE scans ADD COLUMN IF NOT EXISTS completed_at TIMESTAMP WITH TIME ZONE",
    "ALTER TABLE scans ADD COLUMN IF NOT EXISTS failed_at TIMESTAMP WITH TIME ZONE",
    "ALTER TABLE scans ADD COLUMN IF NOT EXISTS error_message TEXT",
    "ALTER TABLE scans ADD COLUMN IF NOT EXISTS evidence_metadata JSONB NOT NULL DEFAULT '{}'::jsonb",
)

_FINDING_COLUMN_UPDATES = (
    "ALTER TABLE findings ADD COLUMN IF NOT EXISTS description TEXT",
    "ALTER TABLE findings ADD COLUMN IF NOT EXISTS help_url VARCHAR(500)",
    "ALTER TABLE findings ADD COLUMN IF NOT EXISTS wcag_refs JSONB NOT NULL DEFAULT '[]'::jsonb",
    "ALTER TABLE findings ADD COLUMN IF NOT EXISTS evidence JSONB",
    "ALTER TABLE findings ADD COLUMN IF NOT EXISTS confidence_score DOUBLE PRECISION",
    "ALTER TABLE findings ADD COLUMN IF NOT EXISTS review_status VARCHAR(50) NOT NULL DEFAULT 'pending'",
    "ALTER TABLE findings ADD COLUMN IF NOT EXISTS evidence_metadata JSONB NOT NULL DEFAULT '{}'::jsonb",
    "ALTER TABLE findings ADD COLUMN IF NOT EXISTS journey_id VARCHAR(36)",
)

_SCAN_EVIDENCE_COLUMN_UPDATES = (
    "ALTER TABLE scan_evidence ADD COLUMN IF NOT EXISTS related_entity_type VARCHAR(80)",
    "ALTER TABLE scan_evidence ADD COLUMN IF NOT EXISTS related_entity_id VARCHAR(36)",
)

_JOURNEY_ENUM_UPDATES = (
    "ALTER TYPE journey_status ADD VALUE IF NOT EXISTS 'running'",
    "ALTER TYPE journey_status ADD VALUE IF NOT EXISTS 'done'",
)

_JOURNEY_COLUMN_UPDATES = (
    "ALTER TABLE journeys ADD COLUMN IF NOT EXISTS executed_at TIMESTAMP WITH TIME ZONE",
    "ALTER TABLE journeys ADD COLUMN IF NOT EXISTS error_message TEXT",
)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    _ensure_scan_lifecycle_schema()
    _ensure_finding_evidence_schema()
    _ensure_scan_evidence_related_entity_schema()
    _ensure_journey_execution_schema()


def _ensure_scan_lifecycle_schema() -> None:
    if engine.dialect.name != "postgresql":
        return

    with engine.connect() as connection:
        autocommit_connection = connection.execution_options(isolation_level="AUTOCOMMIT")
        for statement in _SCAN_ENUM_UPDATES:
            autocommit_connection.execute(text(statement))

    with engine.begin() as connection:
        for statement in _SCAN_COLUMN_UPDATES:
            connection.execute(text(statement))


def _ensure_finding_evidence_schema() -> None:
    if engine.dialect.name != "postgresql":
        return

    with engine.begin() as connection:
        for statement in _FINDING_COLUMN_UPDATES:
            connection.execute(text(statement))


def _ensure_scan_evidence_related_entity_schema() -> None:
    if engine.dialect.name != "postgresql":
        return

    with engine.begin() as connection:
        for statement in _SCAN_EVIDENCE_COLUMN_UPDATES:
            connection.execute(text(statement))


def _ensure_journey_execution_schema() -> None:
    if engine.dialect.name != "postgresql":
        return

    with engine.connect() as connection:
        autocommit_connection = connection.execution_options(isolation_level="AUTOCOMMIT")
        for statement in _JOURNEY_ENUM_UPDATES:
            autocommit_connection.execute(text(statement))

    with engine.begin() as connection:
        for statement in _JOURNEY_COLUMN_UPDATES:
            connection.execute(text(statement))
