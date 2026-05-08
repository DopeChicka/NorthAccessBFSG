from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from app.core.config import settings
from app.evidence.hashing import sha256_bytes
from app.evidence.storage_backend import (
    EvidenceStorageBackend,
    LocalFileStorageBackend,
    S3StorageBackend,
)


@dataclass(frozen=True)
class EvidenceArtifact:
    type: str
    content: bytes
    content_type: str
    extension: str


@dataclass(frozen=True)
class StoredEvidenceArtifact:
    type: str
    storage_backend: str
    storage_path: str
    hash: str
    size_bytes: int
    content_type: str


class EvidenceStorage:
    def __init__(self, backend: EvidenceStorageBackend) -> None:
        self.backend = backend

    def store_artifact(
        self,
        *,
        scan_id: str,
        finding_id: str | None,
        artifact: EvidenceArtifact,
    ) -> StoredEvidenceArtifact:
        artifact_hash = sha256_bytes(artifact.content)
        storage_path = _build_storage_path(
            scan_id=scan_id,
            finding_id=finding_id,
            artifact_type=artifact.type,
            artifact_hash=artifact_hash,
            extension=artifact.extension,
        )
        stored_object = self.backend.put_bytes(
            storage_path=storage_path,
            content=artifact.content,
            content_type=artifact.content_type,
        )

        return StoredEvidenceArtifact(
            type=artifact.type,
            storage_backend=stored_object.backend,
            storage_path=stored_object.storage_path,
            hash=artifact_hash,
            size_bytes=stored_object.size_bytes,
            content_type=artifact.content_type,
        )

    def retrieve_artifact(self, *, storage_path: str) -> bytes:
        return self.backend.get_bytes(storage_path=storage_path)


def get_evidence_storage() -> EvidenceStorage:
    backend_name = settings.evidence_storage_backend.lower().strip()
    if backend_name == "local":
        backend = LocalFileStorageBackend(settings.evidence_local_root)
    elif backend_name == "s3":
        backend = S3StorageBackend(
            bucket=settings.evidence_s3_bucket,
            prefix=settings.evidence_s3_prefix,
            endpoint_url=settings.evidence_s3_endpoint_url,
            region_name=settings.evidence_s3_region,
        )
    else:
        raise ValueError(f"Unsupported evidence storage backend '{backend_name}'")

    return EvidenceStorage(backend)


def _build_storage_path(
    *,
    scan_id: str,
    finding_id: str | None,
    artifact_type: str,
    artifact_hash: str,
    extension: str,
) -> str:
    captured_at = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    scope = finding_id or "global"
    object_id = uuid.uuid4().hex
    clean_extension = extension.lstrip(".")
    return (
        f"scans/{scan_id}/{scope}/{artifact_type}/"
        f"{captured_at}-{artifact_hash[:16]}-{object_id}.{clean_extension}"
    )
