"""Discovery provider adapters."""

from app.discovery.providers.base import DiscoveryProvider, ProviderResult
from app.discovery.providers.google_places_provider import GooglePlacesProvider
from app.discovery.providers.mock_provider import MockDiscoveryProvider

__all__ = [
    "DiscoveryProvider",
    "GooglePlacesProvider",
    "MockDiscoveryProvider",
    "ProviderResult",
]
