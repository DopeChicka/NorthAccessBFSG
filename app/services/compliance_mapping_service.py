from __future__ import annotations

from sqlalchemy.orm import Session

from app.compliance.mapping import map_axe_rule
from app.models import ComplianceMapping, Finding, Scan
from app.services.review_service import auto_create_review_item_for_compliance_mapping


class FindingNotFoundError(Exception):
    pass


class ComplianceMappingNotFoundError(Exception):
    pass


class ScanNotFoundError(Exception):
    pass


def map_finding_compliance(db: Session, finding_id: str) -> ComplianceMapping:
    finding = db.get(Finding, finding_id)
    if finding is None:
        raise FindingNotFoundError(f"Finding not found: {finding_id}")

    mapping = _build_compliance_mapping(finding)
    db.add(mapping)
    db.flush()
    auto_create_review_item_for_compliance_mapping(db, mapping)
    db.commit()
    db.refresh(mapping)
    return mapping


def get_finding_compliance(db: Session, finding_id: str) -> ComplianceMapping:
    finding = db.get(Finding, finding_id)
    if finding is None:
        raise FindingNotFoundError(f"Finding not found: {finding_id}")

    mapping = (
        db.query(ComplianceMapping)
        .filter(ComplianceMapping.finding_id == finding_id)
        .order_by(ComplianceMapping.created_at.desc(), ComplianceMapping.id.desc())
        .first()
    )
    if mapping is None:
        raise ComplianceMappingNotFoundError(
            f"Compliance mapping not found for finding: {finding_id}"
        )
    return mapping


def map_scan_findings_compliance(db: Session, scan_id: str) -> list[ComplianceMapping]:
    scan = db.get(Scan, scan_id)
    if scan is None:
        raise ScanNotFoundError(f"Scan not found: {scan_id}")

    findings = (
        db.query(Finding)
        .filter(Finding.scan_id == scan_id)
        .order_by(Finding.created_at.asc(), Finding.id.asc())
        .all()
    )
    mappings = [_build_compliance_mapping(finding) for finding in findings]
    db.add_all(mappings)
    db.flush()
    for mapping in mappings:
        auto_create_review_item_for_compliance_mapping(db, mapping)
    db.commit()
    for mapping in mappings:
        db.refresh(mapping)
    return mappings


def _build_compliance_mapping(finding: Finding) -> ComplianceMapping:
    reference = map_axe_rule(finding.rule_id)
    evidence = {
        "source": "axe_rule_compliance_mapping",
        "source_rule_id": finding.rule_id,
        "review_required": reference.review_required,
        "mapping_confidence": reference.mapping_confidence,
        "no_legal_conclusion": True,
    }
    return ComplianceMapping(
        finding_id=finding.id,
        source_rule_id=finding.rule_id,
        wcag_refs=list(reference.wcag_refs),
        en_301_549_refs=list(reference.en_301_549_refs),
        bfsg_signal_refs=list(reference.bfsg_signal_refs),
        review_required=reference.review_required,
        confidence_score=reference.mapping_confidence,
        evidence=evidence,
    )
