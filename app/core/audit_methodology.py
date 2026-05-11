from __future__ import annotations

from dataclasses import dataclass

DEFAULT_METHOD_DISCLAIMER = (
    "Technischer Hinweis, keine Rechtsberatung. Manuelle Pruefung empfohlen."
)

AUTOMATED_PRECHECK = "automated_precheck"
MANUAL_REVIEW = "manual_review"
ASSISTED_REVIEW = "assisted_review"


@dataclass(frozen=True)
class FindingMethodology:
    finding_type: str
    category: str
    automation_level: str
    manual_review_required: bool
    responsible_role: str
    recommended_next_step: str
    disclaimer: str = DEFAULT_METHOD_DISCLAIMER


_FINDING_METHODOLOGY_MAP: dict[str, FindingMethodology] = {
    "missing_alt_text": FindingMethodology(
        finding_type="missing_alt_text",
        category="accessibility",
        automation_level=ASSISTED_REVIEW,
        manual_review_required=True,
        responsible_role="content",
        recommended_next_step=(
            "Manuelle Pruefung der Bildaussage und passende Alt-Texte durchfuehren."
        ),
    ),
    "color_contrast_issue": FindingMethodology(
        finding_type="color_contrast_issue",
        category="accessibility",
        automation_level=ASSISTED_REVIEW,
        manual_review_required=True,
        responsible_role="design",
        recommended_next_step=(
            "Kontrastwerte manuell gegen Designsystem und reale Nutzungsszenarien pruefen."
        ),
    ),
    "missing_html_lang": FindingMethodology(
        finding_type="missing_html_lang",
        category="accessibility",
        automation_level=ASSISTED_REVIEW,
        manual_review_required=True,
        responsible_role="developer",
        recommended_next_step=(
            "HTML-Root-Sprache setzen und mit assistiven Technologien gegenpruefen."
        ),
    ),
    "missing_h1": FindingMethodology(
        finding_type="missing_h1",
        category="seo",
        automation_level=AUTOMATED_PRECHECK,
        manual_review_required=False,
        responsible_role="content",
        recommended_next_step=(
            "Inhaltsstruktur ueberarbeiten und semantisch passende Hauptueberschrift setzen."
        ),
    ),
    "unclear_button_label": FindingMethodology(
        finding_type="unclear_button_label",
        category="accessibility",
        automation_level=MANUAL_REVIEW,
        manual_review_required=True,
        responsible_role="ux",
        recommended_next_step=(
            "Button-Texte im Nutzerkontext und mit Screenreader-Output manuell pruefen."
        ),
    ),
    "missing_landmark": FindingMethodology(
        finding_type="missing_landmark",
        category="accessibility",
        automation_level=ASSISTED_REVIEW,
        manual_review_required=True,
        responsible_role="developer",
        recommended_next_step=(
            "Semantische Landmarken ergaenzen und Tastatur-/Screenreader-Navigation pruefen."
        ),
    ),
    "keyboard_navigation_risk": FindingMethodology(
        finding_type="keyboard_navigation_risk",
        category="accessibility",
        automation_level=MANUAL_REVIEW,
        manual_review_required=True,
        responsible_role="auditor",
        recommended_next_step=(
            "Vollstaendige Tastaturnavigation und Fokusreihenfolge manuell testen."
        ),
    ),
    "missing_meta_description": FindingMethodology(
        finding_type="missing_meta_description",
        category="seo",
        automation_level=AUTOMATED_PRECHECK,
        manual_review_required=False,
        responsible_role="content",
        recommended_next_step=(
            "Meta-Description inhaltlich abstimmen und Suchintention manuell reviewen."
        ),
    ),
    "missing_impressum_link": FindingMethodology(
        finding_type="missing_impressum_link",
        category="privacy",
        automation_level=ASSISTED_REVIEW,
        manual_review_required=True,
        responsible_role="auditor",
        recommended_next_step=(
            "Linkpfad und Sichtbarkeit manuell pruefen, danach rechtliche Einordnung extern klaeren."
        ),
    ),
    "missing_privacy_link": FindingMethodology(
        finding_type="missing_privacy_link",
        category="privacy",
        automation_level=ASSISTED_REVIEW,
        manual_review_required=True,
        responsible_role="auditor",
        recommended_next_step=(
            "Datenschutz-Link und Seiteninhalt manuell pruefen, danach rechtliche Einordnung extern klaeren."
        ),
    ),
    "no_https": FindingMethodology(
        finding_type="no_https",
        category="technical",
        automation_level=AUTOMATED_PRECHECK,
        manual_review_required=False,
        responsible_role="developer",
        recommended_next_step=(
            "TLS/HTTPS konfigurieren und Weiterleitungen technisch validieren."
        ),
    ),
}

_ALIASES: dict[str, str] = {
    "image_alt": "missing_alt_text",
    "image_alt_text_missing": "missing_alt_text",
    "color_contrast": "color_contrast_issue",
    "html_has_lang": "missing_html_lang",
    "meta_description_missing": "missing_meta_description",
    "impressum_link_missing": "missing_impressum_link",
    "privacy_link_missing": "missing_privacy_link",
    "https_missing": "no_https",
}


def get_finding_methodology(
    finding_type: str | None,
    *,
    category: str | None = None,
) -> FindingMethodology:
    normalized = _normalize(finding_type)
    mapped_key = _ALIASES.get(normalized, normalized)
    if mapped_key in _FINDING_METHODOLOGY_MAP:
        return _FINDING_METHODOLOGY_MAP[mapped_key]
    return _default_methodology(category=category, finding_type=mapped_key)


def list_finding_methodology() -> dict[str, FindingMethodology]:
    return dict(_FINDING_METHODOLOGY_MAP)


def _default_methodology(
    *,
    category: str | None,
    finding_type: str,
) -> FindingMethodology:
    normalized_category = _normalize(category)
    category_value = normalized_category if normalized_category else "technical"

    if category_value == "accessibility":
        return FindingMethodology(
            finding_type=finding_type or "unknown_accessibility_finding",
            category="accessibility",
            automation_level=ASSISTED_REVIEW,
            manual_review_required=True,
            responsible_role="auditor",
            recommended_next_step=(
                "Automationssignal manuell mit Tastatur, Screenreader und UX-Kontext pruefen."
            ),
        )
    if category_value == "privacy":
        return FindingMethodology(
            finding_type=finding_type or "unknown_privacy_finding",
            category="privacy",
            automation_level=ASSISTED_REVIEW,
            manual_review_required=True,
            responsible_role="auditor",
            recommended_next_step=(
                "Signal manuell pruefen und rechtliche Bewertung ausserhalb der Automation durchfuehren."
            ),
        )
    if category_value == "seo":
        return FindingMethodology(
            finding_type=finding_type or "unknown_seo_finding",
            category="seo",
            automation_level=AUTOMATED_PRECHECK,
            manual_review_required=False,
            responsible_role="content",
            recommended_next_step="Inhaltliche und strukturelle Nachbesserung planen.",
        )

    return FindingMethodology(
        finding_type=finding_type or "unknown_technical_finding",
        category="technical",
        automation_level=AUTOMATED_PRECHECK,
        manual_review_required=False,
        responsible_role="developer",
        recommended_next_step="Technische Ursache pruefen und reproduzierbar beheben.",
    )


def _normalize(value: str | None) -> str:
    if not value:
        return ""
    return value.strip().casefold().replace("-", "_").replace(" ", "_")
