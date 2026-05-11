from __future__ import annotations

from app.core.audit_methodology import (
    ASSISTED_REVIEW,
    AUTOMATED_PRECHECK,
    DEFAULT_METHOD_DISCLAIMER,
    MANUAL_REVIEW,
    get_finding_methodology,
    list_finding_methodology,
)


def test_methodology_includes_required_finding_types() -> None:
    mapping = list_finding_methodology()
    expected = {
        "missing_alt_text",
        "color_contrast_issue",
        "missing_html_lang",
        "missing_h1",
        "unclear_button_label",
        "missing_landmark",
        "keyboard_navigation_risk",
        "missing_meta_description",
        "missing_impressum_link",
        "missing_privacy_link",
        "no_https",
    }
    assert expected.issubset(set(mapping.keys()))


def test_accessibility_defaults_require_manual_review() -> None:
    methodology = get_finding_methodology("unknown_new_issue", category="accessibility")

    assert methodology.category == "accessibility"
    assert methodology.automation_level == ASSISTED_REVIEW
    assert methodology.manual_review_required is True
    assert methodology.responsible_role == "auditor"
    assert methodology.disclaimer == DEFAULT_METHOD_DISCLAIMER


def test_representative_findings_have_expected_roles_and_levels() -> None:
    alt_text = get_finding_methodology("missing_alt_text")
    assert alt_text.category == "accessibility"
    assert alt_text.responsible_role == "content"
    assert alt_text.manual_review_required is True

    keyboard = get_finding_methodology("keyboard_navigation_risk")
    assert keyboard.automation_level == MANUAL_REVIEW
    assert keyboard.manual_review_required is True
    assert keyboard.responsible_role == "auditor"

    https_issue = get_finding_methodology("no_https")
    assert https_issue.category == "technical"
    assert https_issue.automation_level == AUTOMATED_PRECHECK
    assert https_issue.manual_review_required is False
    assert https_issue.responsible_role == "developer"


def test_aliases_resolve_to_expected_mapping() -> None:
    alias_entry = get_finding_methodology("impressum-link-missing")
    canonical_entry = get_finding_methodology("missing_impressum_link")

    assert alias_entry.finding_type == canonical_entry.finding_type
    assert alias_entry.category == "privacy"
    assert alias_entry.manual_review_required is True
