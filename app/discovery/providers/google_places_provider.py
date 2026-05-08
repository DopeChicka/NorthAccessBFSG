"""Google Places API discovery provider adapter.

Google Places results are raw seed candidates only. They are not evidence of BFSG
applicability, legal obligation, or accessibility violations.
"""

from __future__ import annotations

from typing import Any

import httpx

from app.core.config import get_settings
from app.discovery.providers.base import ProviderResult

GOOGLE_PLACES_SOURCE = "google_places"
GOOGLE_PLACES_TEXT_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
GOOGLE_PLACES_FIELD_MASK = ",".join(
    (
        "places.id",
        "places.name",
        "places.displayName",
        "places.formattedAddress",
        "places.nationalPhoneNumber",
        "places.internationalPhoneNumber",
        "places.websiteUri",
        "places.types",
    )
)


class GooglePlacesProviderError(RuntimeError):
    pass


class GooglePlacesDisabledError(GooglePlacesProviderError):
    pass


class GooglePlacesConfigurationError(GooglePlacesProviderError):
    pass


class GooglePlacesProvider:
    source = GOOGLE_PLACES_SOURCE

    def __init__(
        self,
        *,
        api_key: str | None = None,
        enabled: bool | None = None,
        timeout_seconds: int | None = None,
        max_results_per_query: int | None = None,
    ) -> None:
        settings = get_settings()
        self.api_key = api_key if api_key is not None else settings.google_places_api_key
        self.enabled = enabled if enabled is not None else settings.google_places_enabled
        self.timeout_seconds = (
            timeout_seconds
            if timeout_seconds is not None
            else settings.google_places_timeout_seconds
        )
        self.max_results_per_query = (
            max_results_per_query
            if max_results_per_query is not None
            else settings.google_places_max_results_per_query
        )

    def search(self, query_plan: list[dict[str, Any]]) -> list[ProviderResult]:
        self._ensure_enabled()

        results: list[ProviderResult] = []
        for entry in query_plan:
            payload = self._fetch_text_search(entry.get("query_text") or "")
            places = payload.get("places") or payload.get("results") or []
            for place in places[: self.max_results_per_query]:
                results.append(self.map_place_to_result(place, entry))
        return results

    def _ensure_enabled(self) -> None:
        if not self.enabled:
            raise GooglePlacesDisabledError("Google Places API provider is disabled")
        if not self.api_key:
            raise GooglePlacesConfigurationError(
                "Google Places API key is required when provider is enabled"
            )

    def _fetch_text_search(self, query_text: str) -> dict[str, Any]:
        request_payload = {
            "textQuery": query_text,
            "maxResultCount": self.max_results_per_query,
        }
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key or "",
            "X-Goog-FieldMask": GOOGLE_PLACES_FIELD_MASK,
        }
        with httpx.Client(timeout=self.timeout_seconds) as client:
            response = client.post(
                GOOGLE_PLACES_TEXT_SEARCH_URL,
                headers=headers,
                json=request_payload,
            )
            response.raise_for_status()
            return response.json()

    @classmethod
    def map_place_to_result(
        cls, place: dict[str, Any], query_entry: dict[str, Any] | None = None
    ) -> ProviderResult:
        query_entry = query_entry or {}
        display_name = place.get("displayName") or place.get("display_name") or {}
        company_name = (
            display_name.get("text")
            if isinstance(display_name, dict)
            else None
        ) or place.get("name")

        types = place.get("types") or []
        if not isinstance(types, list):
            types = []
        source_reference = place.get("place_id") or place.get("id") or place.get("name")
        raw_data = {
            "provider": cls.source,
            "query_text": query_entry.get("query_text"),
            "keyword_group_id": query_entry.get("keyword_group_id"),
            "keyword": query_entry.get("keyword"),
            "place": place,
        }

        return ProviderResult(
            source=cls.source,
            source_reference=source_reference,
            company_name=company_name,
            domain=place.get("websiteUri") or place.get("website"),
            city=query_entry.get("city"),
            postal_code=query_entry.get("postal_code"),
            address=place.get("formattedAddress") or place.get("formatted_address"),
            phone=(
                place.get("nationalPhoneNumber")
                or place.get("internationalPhoneNumber")
                or place.get("formatted_phone_number")
            ),
            category=types[0] if types else None,
            raw_data=raw_data,
            confidence_score=0.4,
        )


__all__ = [
    "GOOGLE_PLACES_SOURCE",
    "GooglePlacesConfigurationError",
    "GooglePlacesDisabledError",
    "GooglePlacesProvider",
    "GooglePlacesProviderError",
]
