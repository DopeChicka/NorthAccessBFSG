"""Provider interface for discovery candidate sources.

Provider adapters transform stored query-plan entries into candidate-like result
objects. Implementations must not make legal claims about applicability or
violations.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class ProviderResult:
    source: str
    source_reference: str | None = None
    company_name: str | None = None
    domain: str | None = None
    city: str | None = None
    postal_code: str | None = None
    address: str | None = None
    phone: str | None = None
    category: str | None = None
    raw_data: dict[str, Any] | None = None
    confidence_score: float | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["raw_data"] = self.raw_data or {}
        return data


class DiscoveryProvider(Protocol):
    source: str

    def search(self, query_plan: list[dict[str, str]]) -> list[ProviderResult]:
        """Return provider results for query-plan entries."""
