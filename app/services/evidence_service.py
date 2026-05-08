from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.evidence.hashing import chain_hash, evidence_fingerprint
from app.evidence.storage import EvidenceArtifact, get_evidence_storage
from app.models import EvidenceBundle


@dataclass(frozen=True)
class EvidenceBundleSummary:
    id: str
    scan_id: str
    finding_id: str | None
    type: str
    storage_backend: str
    storage_path: str
    content_type: str
    size_bytes: int
    version: int
    hash: str
    previous_hash: str | None
    chain_hash: str
    fingerprint: str | None
    created_at: str

    def as_dict(self) -> dict[str, int | str | None]:
        return {
            "id": self.id,
            "scan_id": self.scan_id,
            "finding_id": self.finding_id,
            "type": self.type,
            "storage_backend": self.storage_backend,
            "storage_path": self.storage_path,
            "content_type": self.content_type,
            "size_bytes": self.size_bytes,
            "version": self.version,
            "hash": self.hash,
            "previous_hash": self.previous_hash,
            "chain_hash": self.chain_hash,
            "fingerprint": self.fingerprint,
            "created_at": self.created_at,
        }


def persist_scan_evidence(
    db: Session, *, scan_id: str, artifacts: list[EvidenceArtifact]
) -> list[EvidenceBundle]:
    return [
        _store_bundle(db, scan_id=scan_id, finding_id=None, artifact=artifact)
        for artifact in artifacts
    ]


def persist_finding_evidence(
    db: Session,
    *,
    scan_id: str,
    finding_id: str,
    artifacts: list[EvidenceArtifact],
) -> list[EvidenceBundle]:
    bundles = [
        _store_bundle(db, scan_id=scan_id, finding_id=finding_id, artifact=artifact)
        for artifact in artifacts
    ]
    fingerprint = evidence_fingerprint(
        finding_id=finding_id, artifact_hashes=[bundle.hash for bundle in bundles]
    )
    for bundle in bundles:
        bundle.fingerprint = fingerprint
    db.flush()
    return bundles


def list_scan_evidence(db: Session, scan_id: str) -> list[EvidenceBundleSummary]:
    bundles = (
        db.query(EvidenceBundle)
        .filter(EvidenceBundle.scan_id == scan_id)
        .order_by(EvidenceBundle.created_at.asc(), EvidenceBundle.id.asc())
        .all()
    )
    return [_to_summary(bundle) for bundle in bundles]


def list_finding_evidence(db: Session, finding_id: str) -> list[EvidenceBundleSummary]:
    bundles = (
        db.query(EvidenceBundle)
        .filter(EvidenceBundle.finding_id == finding_id)
        .order_by(EvidenceBundle.created_at.asc(), EvidenceBundle.id.asc())
        .all()
    )
    return [_to_summary(bundle) for bundle in bundles]


def _store_bundle(
    db: Session,
    *,
    scan_id: str,
    finding_id: str | None,
    artifact: EvidenceArtifact,
) -> EvidenceBundle:
    stored_artifact = get_evidence_storage().store_artifact(
        scan_id=scan_id,
        finding_id=finding_id,
        artifact=artifact,
    )
    version = _next_version(
        db,
        scan_id=scan_id,
        finding_id=finding_id,
        evidence_type=artifact.type,
    )
    previous_chain_hash = _latest_chain_hash(db, scan_id=scan_id)
    bundle_chain_hash = chain_hash(
        previous_chain_hash=previous_chain_hash,
        artifact_hash=stored_artifact.hash,
        scan_id=scan_id,
        finding_id=finding_id,
        evidence_type=artifact.type,
        storage_path=stored_artifact.storage_path,
        version=version,
    )
    bundle = EvidenceBundle(
        scan_id=scan_id,
        finding_id=finding_id,
        type=artifact.type,
        storage_backend=stored_artifact.storage_backend,
        storage_path=stored_artifact.storage_path,
        content_type=stored_artifact.content_type,
        size_bytes=stored_artifact.size_bytes,
        version=version,
        hash=stored_artifact.hash,
        previous_hash=previous_chain_hash,
        chain_hash=bundle_chain_hash,
    )
    db.add(bundle)
    db.flush()
    return bundle


def _next_version(
    db: Session,
    *,
    scan_id: str,
    finding_id: str | None,
    evidence_type: str,
) -> int:
    query = db.query(func.max(EvidenceBundle.version)).filter(
        EvidenceBundle.scan_id == scan_id,
        EvidenceBundle.type == evidence_type,
    )
    if finding_id is None:
        query = query.filter(EvidenceBundle.finding_id.is_(None))
    else:
        query = query.filter(EvidenceBundle.finding_id == finding_id)
    return (query.scalar() or 0) + 1


def _latest_chain_hash(db: Session, *, scan_id: str) -> str | None:
    bundle = (
        db.query(EvidenceBundle)
        .filter(EvidenceBundle.scan_id == scan_id)
        .order_by(EvidenceBundle.created_at.desc(), EvidenceBundle.id.desc())
        .first()
    )
    return bundle.chain_hash if bundle else None


def _to_summary(bundle: EvidenceBundle) -> EvidenceBundleSummary:
    return EvidenceBundleSummary(
        id=bundle.id,
        scan_id=bundle.scan_id,
        finding_id=bundle.finding_id,
        type=bundle.type,
        storage_backend=bundle.storage_backend,
        storage_path=bundle.storage_path,
        content_type=bundle.content_type,
        size_bytes=bundle.size_bytes,
        version=bundle.version,
        hash=bundle.hash,
        previous_hash=bundle.previous_hash,
        chain_hash=bundle.chain_hash,
        fingerprint=bundle.fingerprint,
        created_at=bundle.created_at.isoformat(),
    )
