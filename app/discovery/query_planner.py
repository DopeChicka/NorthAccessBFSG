"""Deterministic dry-run query planner for lead discovery.

This module prepares internal search queries only. It does not call external
providers and does not scrape websites.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.discovery.keywords import get_keyword_groups
from app.discovery.place_resolver import PlaceMatch, resolve_city


@dataclass(frozen=True)
class QueryPlan:
    city: str
    postal_codes: list[str]
    keyword_groups: list[dict[str, object]]
    query_plan: list[dict[str, str]]


def get_enabled_keyword_groups() -> list[dict[str, object]]:
    return [group for group in get_keyword_groups() if group.get("enabled") is True]


def _unique_places_by_postal_code(places: list[PlaceMatch]) -> list[PlaceMatch]:
    by_postal_code = {place.postal_code: place for place in places}
    return [by_postal_code[postal_code] for postal_code in sorted(by_postal_code)]


def build_query_plan(city: str) -> QueryPlan:
    places = _unique_places_by_postal_code(resolve_city(city))
    keyword_groups = get_enabled_keyword_groups()
    query_entries: list[dict[str, str]] = []

    for place in places:
        for group in keyword_groups:
            group_id = str(group["group_id"])
            for keyword in group["keywords"]:
                keyword_text = str(keyword)
                query_entries.append(
                    {
                        "city": place.city,
                        "postal_code": place.postal_code,
                        "keyword_group_id": group_id,
                        "keyword": keyword_text,
                        "query_text": f"{place.city} {place.postal_code} {keyword_text}",
                    }
                )

    return QueryPlan(
        city=places[0].city,
        postal_codes=[place.postal_code for place in places],
        keyword_groups=keyword_groups,
        query_plan=query_entries,
    )
