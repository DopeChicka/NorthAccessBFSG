"""BFSG-relevant keyword groups for future lead discovery provider searches."""

from __future__ import annotations

from copy import deepcopy

KEYWORD_GROUPS = [
    {
        "group_id": "ecommerce",
        "label": "E-Commerce",
        "keywords": ["online shop", "webshop", "e-commerce", "versandhandel"],
        "bfsg_relevance_reason": "Online retail services can fall within BFSG-relevant consumer-facing digital services.",
        "enabled": True,
    },
    {
        "group_id": "banking",
        "label": "Banking",
        "keywords": ["bank", "sparkasse", "kredit", "online banking"],
        "bfsg_relevance_reason": "Banking and financial self-service channels are a core BFSG-relevant service area.",
        "enabled": True,
    },
    {
        "group_id": "transport",
        "label": "Transport",
        "keywords": ["verkehrsbetriebe", "bahn", "bus", "ticket"],
        "bfsg_relevance_reason": "Passenger transport information and ticketing services are relevant for accessibility discovery.",
        "enabled": True,
    },
    {
        "group_id": "booking",
        "label": "Booking",
        "keywords": ["buchung", "reservierung", "hotel", "reise"],
        "bfsg_relevance_reason": "Booking and reservation services can be consumer-facing digital transaction services.",
        "enabled": True,
    },
    {
        "group_id": "healthcare_services",
        "label": "Healthcare Services",
        "keywords": ["terminbuchung", "arzt", "klinik", "apotheke"],
        "bfsg_relevance_reason": "Healthcare service portals are useful candidates for later accessibility audit discovery.",
        "enabled": True,
    },
    {
        "group_id": "telecom",
        "label": "Telecom",
        "keywords": ["telekommunikation", "internet", "mobilfunk", "dsl"],
        "bfsg_relevance_reason": "Telecom providers commonly operate BFSG-relevant consumer portals and ordering flows.",
        "enabled": True,
    },
    {
        "group_id": "public_services_candidate",
        "label": "Public Services Candidate",
        "keywords": ["stadtportal", "buergerdienst", "terminvereinbarung", "verwaltung"],
        "bfsg_relevance_reason": "Public service portals are discovery candidates, while legal applicability must be assessed later.",
        "enabled": True,
    },
]


def get_keyword_groups() -> list[dict[str, object]]:
    return deepcopy(KEYWORD_GROUPS)
