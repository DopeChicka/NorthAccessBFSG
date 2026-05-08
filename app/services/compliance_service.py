from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.compliance.rule_engine import ComplianceMapping, get_rule_engine
from app.models import ComplianceFinding, Finding, Scan


class ScanNotFoundError(Exception):
    pass


@dataclass(frozen=True)
class ComplianceRunSummary:
    scan_id: str
    mapping_version: str
    total_findings: int
    mapped_findings: int
    critical_count: int
    high_count: int
    compliance_coverage_score: float

    def as_dict(self) -> dict[str, int | float | str]:
        return {
            "scan_id": self.scan_id,
            "mapping_version": self.mapping_version,
            "total_findings": self.total_findings,
            "mapped_findings": self.mapped_findings,
            "critical_count": self.critical_count,
            "high_count": self.high_count,
            "compliance_coverage_score": self.compliance_coverage_score,
        }


def run_compliance_mapping(db: Session, scan_id: str) -> ComplianceRunSummary:
    scan = db.get(Scan, scan_id)
    if scan is None:
        raise ScanNotFoundError(f"Scan {scan_id} was not found")

    raw_findings = (
        db.query(Finding)
        .filter(Finding.scan_id == scan_id)
        .order_by(Finding.id.asc())
        .all()
    )
    rule_engine = get_rule_engine()
    mapping_version = rule_engine.mapping_version
    enriched_findings: list[ComplianceFinding] = []
    raw_finding_ids = [finding.id for finding in raw_findings]

    for raw_finding in raw_findings:
        mapping = rule_engine.enrich_finding(raw_finding)
        enriched_findings.append(
            _upsert_compliance_finding(
                db,
                raw_finding=raw_finding,
                mapping=mapping,
            )
        )

    stale_query = db.query(ComplianceFinding).filter(
        ComplianceFinding.scan_id == scan_id,
        ComplianceFinding.mapping_version == mapping_version,
    )
    if raw_finding_ids:
        stale_query.filter(~ComplianceFinding.finding_id.in_(raw_finding_ids)).delete(
            synchronize_session=False
        )
    else:
        stale_query.delete(synchronize_session=False)

    db.commit()

    critical_count = sum(
        1 for finding in enriched_findings if finding.normalized_severity == "critical"
    )
    high_count = sum(
        1 for finding in enriched_findings if finding.normalized_severity == "high"
    )
    mapped_findings = sum(
        1
        for finding in enriched_findings
        if finding.wcag_refs and finding.en_refs and finding.bfsg_refs
    )
    total_findings = len(raw_findings)
    compliance_coverage_score = (
        1.0 if total_findings == 0 else round(mapped_findings / total_findings, 4)
    )

    return ComplianceRunSummary(
        scan_id=scan_id,
        mapping_version=mapping_version,
        total_findings=total_findings,
        mapped_findings=mapped_findings,
        critical_count=critical_count,
        high_count=high_count,
        compliance_coverage_score=compliance_coverage_score,
    )


def _upsert_compliance_finding(
    db: Session, *, raw_finding: Finding, mapping: ComplianceMapping
) -> ComplianceFinding:
    compliance_finding = (
        db.query(ComplianceFinding)
        .filter(
            ComplianceFinding.finding_id == raw_finding.id,
            ComplianceFinding.mapping_version == mapping.mapping_version,
        )
        .one_or_none()
    )

    if compliance_finding is None:
        compliance_finding = ComplianceFinding(
            scan_id=raw_finding.scan_id,
            finding_id=raw_finding.id,
            rule_id=raw_finding.rule_id,
            mapping_version=mapping.mapping_version,
        )
        db.add(compliance_finding)

    compliance_finding.scan_id = raw_finding.scan_id
    compliance_finding.rule_id = raw_finding.rule_id
    compliance_finding.wcag_refs = mapping.wcag_refs
    compliance_finding.en_refs = mapping.en_refs
    compliance_finding.bfsg_refs = mapping.bfsg_refs
    compliance_finding.bfsg_category = mapping.bfsg_category
    compliance_finding.normalized_severity = mapping.normalized_severity
    compliance_finding.compliance_confidence_score = (
        mapping.compliance_confidence_score
    )
    compliance_finding.mapping_metadata = mapping.mapping_metadata

    return compliance_finding
