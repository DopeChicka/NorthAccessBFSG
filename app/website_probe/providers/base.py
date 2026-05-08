"""Provider interface for lightweight website probe signals.

Website probe results are routing signals only. They are not accessibility scan
results, legal conclusions, or BFSG violation findings.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Protocol

from app.models.lead_candidate import LeadCandidate


@dataclass(frozen=True)
class WebsiteProbeResult:
    url: str | None
    normalized_domain: str | None
    status: str
    http_status: int | None = None
    has_homepage_signal: bool | None = None
    has_impressum_signal: bool | None = None
    has_login_signal: bool | None = None
    has_shop_signal: bool | None = None
    has_booking_signal: bool | None = None
    has_checkout_signal: bool | None = None
    has_b2c_transaction_signal: bool | None = None
    evidence: dict[str, Any] | None = None
    confidence_score: float | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["evidence"] = self.evidence or {}
        return data


class WebsiteProbeProvider(Protocol):
    def probe(self, candidate: LeadCandidate) -> WebsiteProbeResult:
        """Return lightweight website signals for a lead candidate."""
