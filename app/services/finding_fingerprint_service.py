from __future__ import annotations

import hashlib
import json
import re
from typing import Any


def build_finding_fingerprint(finding) -> str:
    parts = {
        "rule_id": _normalize_text(getattr(finding, "rule_id", "")),
        "severity": _normalize_text(getattr(finding, "severity", "")),
        "description": _normalize_text(getattr(finding, "description", "") or ""),
        "target": _normalize_target(
            getattr(finding, "evidence", None),
            getattr(finding, "evidence_metadata", None),
        ),
    }
    payload = json.dumps(parts, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().casefold())


def _normalize_target(*sources: dict[str, Any] | None) -> str:
    for source in sources:
        target = _target_from_source(source or {})
        if target:
            return _normalize_text(target)
    return ""


def _target_from_source(source: dict[str, Any]) -> str:
    for key in ("selector", "target", "evidence_target"):
        value = source.get(key)
        if value:
            return _stringify_target(value)

    sample_targets = source.get("sample_targets")
    if sample_targets:
        return _stringify_target(sample_targets[0])

    nodes = source.get("nodes")
    if nodes and isinstance(nodes, list):
        first_node = nodes[0]
        if isinstance(first_node, dict):
            return _stringify_target(first_node.get("target", ""))
    return ""


def _stringify_target(value: Any) -> str:
    if isinstance(value, list):
        return " ".join(str(item) for item in value)
    return str(value)
