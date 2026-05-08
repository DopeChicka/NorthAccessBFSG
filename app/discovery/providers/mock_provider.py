"""Deterministic mock provider for discovery candidate persistence tests.

This adapter creates obvious test data only. It does not call external services,
does not scrape, and does not represent real businesses.
"""

from __future__ import annotations

import re

from app.discovery.providers.base import ProviderResult

MAX_MOCK_RESULTS = 10
_SLUG_PATTERN = re.compile(r"[^a-z0-9]+")


def _title_keyword(keyword: str) -> str:
    return " ".join(part.capitalize() for part in keyword.split())


def _slug(value: str) -> str:
    normalized = value.casefold().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    slug = _SLUG_PATTERN.sub("-", normalized).strip("-")
    return slug or "unknown"


class MockDiscoveryProvider:
    source = "mock"

    def __init__(self, max_results: int = MAX_MOCK_RESULTS) -> None:
        self.max_results = max_results

    def search(self, query_plan: list[dict[str, str]]) -> list[ProviderResult]:
        results: list[ProviderResult] = []
        for entry in query_plan[: self.max_results]:
            city = entry.get("city") or "Unknown City"
            postal_code = entry.get("postal_code") or "00000"
            keyword = entry.get("keyword") or "unknown"
            keyword_group_id = entry.get("keyword_group_id") or "unknown"
            query_text = entry.get("query_text") or ""
            reference = f"mock:{_slug(city)}:{postal_code}:{_slug(keyword_group_id)}:{_slug(keyword)}"

            results.append(
                ProviderResult(
                    source=self.source,
                    source_reference=reference,
                    company_name=f"Mock Candidate {city} {postal_code} {_title_keyword(keyword)}",
                    domain=None,
                    city=city,
                    postal_code=postal_code,
                    address=None,
                    phone=None,
                    category=keyword_group_id,
                    raw_data={
                        "provider": self.source,
                        "mock": True,
                        "query_text": query_text,
                        "keyword_group_id": keyword_group_id,
                        "keyword": keyword,
                    },
                    confidence_score=0.5,
                )
            )
        return results
