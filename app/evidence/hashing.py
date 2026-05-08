from __future__ import annotations

import hashlib
import json
from typing import Any


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def sha256_text(content: str) -> str:
    return sha256_bytes(content.encode("utf-8"))


def canonical_json(value: Any) -> str:
    return json.dumps(value, default=str, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def sha256_json(value: Any) -> str:
    return sha256_text(canonical_json(value))


def evidence_fingerprint(*, finding_id: str, artifact_hashes: list[str]) -> str:
    payload = {
        "artifact_hashes": sorted(artifact_hashes),
        "finding_id": finding_id,
    }
    return sha256_json(payload)


def chain_hash(
    *,
    previous_chain_hash: str | None,
    artifact_hash: str,
    scan_id: str,
    finding_id: str | None,
    evidence_type: str,
    storage_path: str,
    version: int,
) -> str:
    payload = {
        "artifact_hash": artifact_hash,
        "evidence_type": evidence_type,
        "finding_id": finding_id,
        "previous_chain_hash": previous_chain_hash,
        "scan_id": scan_id,
        "storage_path": storage_path,
        "version": version,
    }
    return sha256_json(payload)
