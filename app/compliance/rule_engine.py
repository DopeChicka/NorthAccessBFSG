from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.models import Finding

_RULES_PATH = Path(__file__).parent / "rules" / "wcag_en_bfsg_map.json"
_WCAG_DOTTED_RE = re.compile(r"\b([1-4])\.(\d+)\.(\d+)\b")
_WCAG_TAG_RE = re.compile(r"^wcag([1-4])(\d)(\d+)$", re.IGNORECASE)
_DEFAULT_SEVERITY_MAPPING = {
    "critical": "critical",
    "serious": "high",
    "high": "high",
    "moderate": "medium",
    "medium": "medium",
    "minor": "low",
    "low": "low",
    "info": "info",
    "unknown": "info",
}
_BFSG_CATEGORY_BY_WCAG_PRINCIPLE = {
    "1": "perceivable_content_and_information",
    "2": "operable_interface_and_navigation",
    "3": "understandable_information_and_inputs",
    "4": "robust_assistive_technology_compatibility",
}


@dataclass(frozen=True)
class ComplianceMapping:
    rule_id: str
    wcag_refs: list[str]
    en_refs: list[str]
    bfsg_refs: list[str]
    bfsg_category: str
    normalized_severity: str
    compliance_confidence_score: float
    mapping_version: str
    mapping_metadata: dict[str, Any]


class ComplianceRuleEngine:
    def __init__(self, rules_path: Path = _RULES_PATH) -> None:
        self.rules_path = rules_path
        self._raw_rules_text = rules_path.read_text(encoding="utf-8")
        self._rules_hash = hashlib.sha256(self._raw_rules_text.encode("utf-8")).hexdigest()
        self.dataset = json.loads(self._raw_rules_text)
        self.rules_by_id = {
            rule["rule_id"]: rule for rule in self.dataset.get("rules", [])
        }
        self.severity_rules = self.dataset.get("severity_normalization_rules", {})
        self.mapping_version = f"{self.dataset['version']}:{self._rules_hash[:12]}"

    def enrich_finding(self, finding: Finding) -> ComplianceMapping:
        rule = self.rules_by_id.get(finding.rule_id)
        raw_wcag_refs = _normalize_wcag_refs(finding.wcag_refs or [])

        if rule is not None:
            wcag_refs = _normalize_wcag_refs(rule.get("wcag_references", [])) or raw_wcag_refs
            en_refs = sorted(set(rule.get("en_301_549_references", [])))
            bfsg_category = rule.get("bfsg_category") or _derive_bfsg_category(wcag_refs)
            normalized_severity = self._normalize_severity(
                finding.severity, rule.get("severity_mapping", {})
            )
            source = "rule_dataset"
            base_confidence = 0.95
        else:
            wcag_refs = raw_wcag_refs
            en_refs = [_wcag_to_en_301_549_ref(ref) for ref in wcag_refs]
            bfsg_category = _derive_bfsg_category(wcag_refs)
            normalized_severity = self._normalize_severity(finding.severity, {})
            source = "wcag_fallback"
            base_confidence = 0.7 if wcag_refs else 0.4

        en_refs = sorted({ref for ref in en_refs if ref})
        bfsg_refs = [f"BFSG:{bfsg_category}"] if bfsg_category else []
        raw_confidence = finding.confidence_score if finding.confidence_score is not None else 0.75
        compliance_confidence_score = round(
            min(0.99, (raw_confidence * 0.7) + (base_confidence * 0.3)), 4
        )

        return ComplianceMapping(
            rule_id=finding.rule_id,
            wcag_refs=wcag_refs,
            en_refs=en_refs,
            bfsg_refs=bfsg_refs,
            bfsg_category=bfsg_category,
            normalized_severity=normalized_severity,
            compliance_confidence_score=compliance_confidence_score,
            mapping_version=self.mapping_version,
            mapping_metadata={
                "source": source,
                "rules_file": str(self.rules_path.name),
                "rules_version": self.dataset["version"],
                "rules_sha256": self._rules_hash,
                "raw_rule_id": finding.rule_id,
                "raw_severity": finding.severity,
                "raw_wcag_refs": raw_wcag_refs,
                "standards": self.dataset.get("standard_versions", {}),
            },
        )

    def _normalize_severity(
        self, raw_severity: str | None, severity_mapping: dict[str, Any]
    ) -> str:
        value = (raw_severity or "unknown").lower().strip()
        strategy = severity_mapping.get("strategy")
        if strategy:
            strategy_mapping = self.severity_rules.get(strategy, {})
            normalized = strategy_mapping.get(value)
            if normalized:
                return normalized

        normalized = _DEFAULT_SEVERITY_MAPPING.get(value)
        if normalized:
            return normalized

        return severity_mapping.get("default", "info")


def _normalize_wcag_refs(values: list[str]) -> list[str]:
    refs: set[str] = set()
    for value in values:
        item = str(value).strip()
        dotted_match = _WCAG_DOTTED_RE.search(item)
        if dotted_match:
            refs.add(".".join(dotted_match.groups()))
            continue

        tag_match = _WCAG_TAG_RE.match(item)
        if tag_match:
            refs.add(".".join(tag_match.groups()))

    return sorted(refs, key=_wcag_sort_key)


def _wcag_to_en_301_549_ref(wcag_ref: str) -> str:
    parts = wcag_ref.split(".")
    if len(parts) != 3 or parts[0] not in _BFSG_CATEGORY_BY_WCAG_PRINCIPLE:
        return ""
    return f"9.{parts[0]}.{parts[1]}.{parts[2]}"


def _derive_bfsg_category(wcag_refs: list[str]) -> str:
    if not wcag_refs:
        return "unmapped_accessibility_risk"

    principle = wcag_refs[0].split(".", 1)[0]
    return _BFSG_CATEGORY_BY_WCAG_PRINCIPLE.get(
        principle, "unmapped_accessibility_risk"
    )


def _wcag_sort_key(wcag_ref: str) -> tuple[int, int, int]:
    parts = wcag_ref.split(".")
    return tuple(int(part) for part in parts)  # type: ignore[return-value]


@lru_cache
def get_rule_engine() -> ComplianceRuleEngine:
    return ComplianceRuleEngine()
