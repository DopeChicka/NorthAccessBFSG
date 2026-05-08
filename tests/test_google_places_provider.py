import socket

import pytest

from app.discovery.providers.google_places_provider import (
    GooglePlacesConfigurationError,
    GooglePlacesDisabledError,
    GooglePlacesProvider,
)


QUERY_PLAN = [
    {
        "city": "Lübeck",
        "postal_code": "23552",
        "keyword_group_id": "ecommerce",
        "keyword": "online shop",
        "query_text": "Lübeck 23552 online shop",
    }
]


class StubGooglePlacesProvider(GooglePlacesProvider):
    def _fetch_text_search(self, query_text: str):
        return {
            "places": [
                {
                    "id": "places/mock-place-id",
                    "displayName": {"text": "Example Seed Company"},
                    "websiteUri": "https://example.test",
                    "formattedAddress": "Example Street 1, 23552 Lübeck",
                    "nationalPhoneNumber": "+49 451 000000",
                    "types": ["store", "point_of_interest"],
                }
            ]
        }


def test_google_places_provider_fails_when_disabled() -> None:
    provider = GooglePlacesProvider(enabled=False, api_key="test-key")

    with pytest.raises(GooglePlacesDisabledError, match="provider is disabled"):
        provider.search(QUERY_PLAN)


def test_google_places_provider_fails_when_api_key_missing() -> None:
    provider = GooglePlacesProvider(enabled=True, api_key="")

    with pytest.raises(GooglePlacesConfigurationError, match="API key is required"):
        provider.search(QUERY_PLAN)


def test_google_places_response_mapping_to_provider_result() -> None:
    place = {
        "place_id": "legacy-place-id",
        "displayName": {"text": "Mapped Seed Company"},
        "websiteUri": "https://mapped.example",
        "formattedAddress": "Mapped Street 2, 23552 Lübeck",
        "internationalPhoneNumber": "+49 451 111111",
        "types": ["bank", "finance"],
    }

    result = GooglePlacesProvider.map_place_to_result(place, QUERY_PLAN[0])

    assert result.source == "google_places"
    assert result.source_reference == "legacy-place-id"
    assert result.company_name == "Mapped Seed Company"
    assert result.domain == "https://mapped.example"
    assert result.address == "Mapped Street 2, 23552 Lübeck"
    assert result.phone == "+49 451 111111"
    assert result.category == "bank"
    assert result.city == "Lübeck"
    assert result.postal_code == "23552"
    assert result.raw_data["query_text"] == "Lübeck 23552 online shop"
    assert result.raw_data["keyword_group_id"] == "ecommerce"
    assert result.raw_data["place"] == place


def test_google_places_provider_search_can_be_mocked_without_network(monkeypatch) -> None:
    def fail_network(*args, **kwargs):
        raise AssertionError("network access is not allowed in this test")

    monkeypatch.setattr(socket, "create_connection", fail_network)

    provider = StubGooglePlacesProvider(enabled=True, api_key="test-key")
    results = provider.search(QUERY_PLAN)

    assert len(results) == 1
    assert results[0].source == "google_places"
    assert results[0].source_reference == "places/mock-place-id"
    assert results[0].company_name == "Example Seed Company"
