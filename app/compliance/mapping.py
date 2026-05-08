from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AxeRuleComplianceReference:
    wcag_refs: list[str]
    en_301_549_refs: list[str]
    bfsg_signal_refs: list[str]
    review_required: bool
    mapping_confidence: float


LOW_CONFIDENCE = 0.2

UNKNOWN_AXE_RULE_MAPPING = AxeRuleComplianceReference(
    wcag_refs=[],
    en_301_549_refs=[],
    bfsg_signal_refs=[],
    review_required=True,
    mapping_confidence=LOW_CONFIDENCE,
)

AXE_RULE_MAPPINGS: dict[str, AxeRuleComplianceReference] = {
    "button-name": AxeRuleComplianceReference(
        wcag_refs=["wcag412"],
        en_301_549_refs=["EN 301 549 9.4.1.2"],
        bfsg_signal_refs=["bfsg_name_role_value_signal"],
        review_required=True,
        mapping_confidence=0.9,
    ),
    "color-contrast": AxeRuleComplianceReference(
        wcag_refs=["wcag143"],
        en_301_549_refs=["EN 301 549 9.1.4.3"],
        bfsg_signal_refs=["bfsg_visual_contrast_signal"],
        review_required=True,
        mapping_confidence=0.9,
    ),
    "document-title": AxeRuleComplianceReference(
        wcag_refs=["wcag242"],
        en_301_549_refs=["EN 301 549 9.2.4.2"],
        bfsg_signal_refs=["bfsg_page_identification_signal"],
        review_required=True,
        mapping_confidence=0.85,
    ),
    "html-has-lang": AxeRuleComplianceReference(
        wcag_refs=["wcag311"],
        en_301_549_refs=["EN 301 549 9.3.1.1"],
        bfsg_signal_refs=["bfsg_language_signal"],
        review_required=True,
        mapping_confidence=0.85,
    ),
    "image-alt": AxeRuleComplianceReference(
        wcag_refs=["wcag111"],
        en_301_549_refs=["EN 301 549 9.1.1.1"],
        bfsg_signal_refs=["bfsg_non_text_content_signal"],
        review_required=True,
        mapping_confidence=0.9,
    ),
    "input-image-alt": AxeRuleComplianceReference(
        wcag_refs=["wcag111"],
        en_301_549_refs=["EN 301 549 9.1.1.1"],
        bfsg_signal_refs=["bfsg_non_text_content_signal"],
        review_required=True,
        mapping_confidence=0.85,
    ),
    "label": AxeRuleComplianceReference(
        wcag_refs=["wcag131", "wcag332"],
        en_301_549_refs=["EN 301 549 9.1.3.1", "EN 301 549 9.3.3.2"],
        bfsg_signal_refs=["bfsg_form_input_signal"],
        review_required=True,
        mapping_confidence=0.88,
    ),
    "link-name": AxeRuleComplianceReference(
        wcag_refs=["wcag244", "wcag412"],
        en_301_549_refs=["EN 301 549 9.2.4.4", "EN 301 549 9.4.1.2"],
        bfsg_signal_refs=["bfsg_link_purpose_signal"],
        review_required=True,
        mapping_confidence=0.88,
    ),
    "meta-viewport": AxeRuleComplianceReference(
        wcag_refs=["wcag144"],
        en_301_549_refs=["EN 301 549 9.1.4.4"],
        bfsg_signal_refs=["bfsg_resize_text_signal"],
        review_required=True,
        mapping_confidence=0.8,
    ),
    "region": AxeRuleComplianceReference(
        wcag_refs=["wcag131"],
        en_301_549_refs=["EN 301 549 9.1.3.1"],
        bfsg_signal_refs=["bfsg_page_structure_signal"],
        review_required=True,
        mapping_confidence=0.75,
    ),
}


def map_axe_rule(rule_id: str | None) -> AxeRuleComplianceReference:
    normalized_rule_id = (rule_id or "").strip()
    return AXE_RULE_MAPPINGS.get(normalized_rule_id, UNKNOWN_AXE_RULE_MAPPING)
