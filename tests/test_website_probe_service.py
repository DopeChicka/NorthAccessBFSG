import json
import socket

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.db.base import Base
from app.models import (  # noqa: F401
    CompanyEnrichment,
    CompanyQualification,
    DiscoveryRun,
    DiscoveryRunStatus,
    LeadCandidate,
    PromotionDecision,
    PromotionDecisionStatus,
    WebsiteProbe,
)
from app.services.company_qualification_service import LeadCandidateNotFoundError
from app.services.website_probe_service import (
    run_live_website_probe,
    run_mock_website_probe,
)
from app.website_probe.providers.http_provider import (
    HttpFetchResult,
    HttpWebsiteProbeProvider,
    LiveWebsiteProbeDisabledError,
)


@pytest.fixture()
def db_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    TestingSessionLocal = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)

    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


def _create_run(db_session: Session) -> DiscoveryRun:
    discovery_run = DiscoveryRun(
        city="Lübeck",
        normalized_city="luebeck",
        status=DiscoveryRunStatus.done,
        keyword_groups=[],
        postal_codes=["23552"],
        query_plan=[],
    )
    db_session.add(discovery_run)
    db_session.commit()
    db_session.refresh(discovery_run)
    return discovery_run


def _create_candidate(
    db_session: Session,
    *,
    domain: str | None = None,
    category: str | None = "ecommerce",
    raw_data: dict | None = None,
) -> LeadCandidate:
    discovery_run = _create_run(db_session)
    candidate = LeadCandidate(
        discovery_run_id=discovery_run.id,
        source="google_places",
        source_reference="places/seed",
        company_name="Seed Candidate GmbH",
        domain=domain,
        city="Lübeck",
        postal_code="23552",
        category=category,
        raw_data=raw_data or {},
    )
    db_session.add(candidate)
    db_session.commit()
    db_session.refresh(candidate)
    return candidate


def _add_promotion(
    db_session: Session,
    candidate: LeadCandidate,
    *,
    status: PromotionDecisionStatus,
) -> PromotionDecision:
    decision = PromotionDecision(
        lead_candidate_id=candidate.id,
        status=status,
        reason_code="test_reason",
        reasons={"test": True, "no_legal_conclusion": True},
        confidence_score=0.5,
    )
    db_session.add(decision)
    db_session.commit()
    db_session.refresh(decision)
    return decision


def test_unknown_candidate_fails_clearly(db_session: Session) -> None:
    with pytest.raises(LeadCandidateNotFoundError, match="Lead candidate not found: missing"):
        run_mock_website_probe(db_session, "missing")


def test_candidate_without_domain_produces_skipped_missing_domain(db_session: Session) -> None:
    candidate = _create_candidate(db_session, domain=None)

    probe = run_mock_website_probe(db_session, candidate.id)

    assert probe.status.value == "skipped"
    assert probe.url is None
    assert probe.normalized_domain is None
    assert probe.evidence["missing_domain"] is True
    assert probe.evidence["reason"] == "missing_domain"


def test_ecommerce_candidate_with_domain_produces_transaction_signals(
    db_session: Session,
) -> None:
    candidate = _create_candidate(
        db_session,
        domain="https://shop.example",
        category="ecommerce",
    )

    probe = run_mock_website_probe(db_session, candidate.id)

    assert probe.status.value == "reachable"
    assert probe.http_status == 200
    assert probe.normalized_domain == "shop.example"
    assert probe.has_homepage_signal is True
    assert probe.has_impressum_signal is True
    assert probe.has_shop_signal is True
    assert probe.has_checkout_signal is True
    assert probe.has_b2c_transaction_signal is True


def test_rejected_promotion_produces_skipped_probe(db_session: Session) -> None:
    candidate = _create_candidate(db_session, domain="https://shop.example")
    promotion = _add_promotion(
        db_session,
        candidate,
        status=PromotionDecisionStatus.rejected,
    )

    probe = run_mock_website_probe(db_session, candidate.id)

    assert probe.status.value == "skipped"
    assert probe.promotion_decision_id == promotion.id
    assert probe.evidence["reason"] == "rejected_by_promotion_gate"
    assert probe.evidence["promotion_status"] == "rejected"


def test_needs_review_promotion_is_included_in_evidence(db_session: Session) -> None:
    candidate = _create_candidate(db_session, domain="https://booking.example", category="booking")
    promotion = _add_promotion(
        db_session,
        candidate,
        status=PromotionDecisionStatus.needs_review,
    )

    probe = run_mock_website_probe(db_session, candidate.id)

    assert probe.status.value == "reachable"
    assert probe.promotion_decision_id == promotion.id
    assert probe.evidence["promotion_status"] == "needs_review"
    assert probe.evidence["promotion_decision_id"] == promotion.id
    assert probe.has_booking_signal is True


def test_probe_fields_do_not_contain_forbidden_legal_claims(db_session: Session) -> None:
    candidate = _create_candidate(db_session, domain="https://shop.example", category="ecommerce")

    probe = run_mock_website_probe(db_session, candidate.id)
    text = json.dumps(probe.evidence, sort_keys=True).casefold()

    assert "legally obligated" not in text
    assert "violation" not in text
    assert "violates" not in text
    assert probe.evidence["no_legal_conclusion"] is True


def test_website_probe_makes_no_external_network_calls(monkeypatch, db_session: Session) -> None:
    def fail_network(*args, **kwargs):
        raise AssertionError("network access is not allowed in website probe")

    monkeypatch.setattr(socket, "create_connection", fail_network)
    candidate = _create_candidate(db_session, domain="https://shop.example")

    probe = run_mock_website_probe(db_session, candidate.id)

    assert probe.status.value == "reachable"


def test_live_provider_fails_clearly_when_disabled(db_session: Session) -> None:
    candidate = _create_candidate(db_session, domain="https://shop.example")
    provider = HttpWebsiteProbeProvider(
        settings_=Settings(website_probe_live_enabled=False)
    )

    with pytest.raises(LiveWebsiteProbeDisabledError, match="Live website probe is disabled"):
        provider.probe(candidate)


def test_live_probe_without_domain_persists_skipped_missing_domain(
    db_session: Session,
) -> None:
    candidate = _create_candidate(db_session, domain=None)
    provider = HttpWebsiteProbeProvider(settings_=Settings(website_probe_live_enabled=True))

    probe = run_live_website_probe(db_session, candidate.id, provider=provider)

    assert probe.status.value == "skipped"
    assert probe.url is None
    assert probe.normalized_domain is None
    assert probe.evidence["provider"] == "live_http_website_probe"
    assert probe.evidence["reason"] == "missing_domain"
    assert probe.evidence["missing_domain"] is True
    assert probe.evidence["no_legal_conclusion"] is True


def test_live_provider_extracts_http_signals_from_single_response(
    db_session: Session,
) -> None:
    candidate = _create_candidate(db_session, domain="signal.example")

    def fake_fetcher(url: str, settings_: Settings) -> HttpFetchResult:
        assert url == "https://signal.example"
        assert settings_.website_probe_timeout_seconds == 3
        return HttpFetchResult(
            url=url,
            status_code=200,
            body=(
                b"<html><a href='/impressum'>Impressum</a>"
                b"<a href='/login'>Login</a>"
                b"<a href='/shop'>Shop</a>"
                b"<a href='/cart'>Cart</a>"
                b"<a href='/checkout'>Checkout</a>"
                b"<a href='/booking'>Booking</a></html>"
            ),
        )

    provider = HttpWebsiteProbeProvider(
        settings_=Settings(
            website_probe_live_enabled=True,
            website_probe_timeout_seconds=3,
        ),
        fetcher=fake_fetcher,
    )

    probe = run_live_website_probe(db_session, candidate.id, provider=provider)

    assert probe.status.value == "reachable"
    assert probe.url == "https://signal.example"
    assert probe.normalized_domain == "signal.example"
    assert probe.http_status == 200
    assert probe.has_homepage_signal is True
    assert probe.has_impressum_signal is True
    assert probe.has_login_signal is True
    assert probe.has_shop_signal is True
    assert probe.has_booking_signal is True
    assert probe.has_checkout_signal is True
    assert probe.has_b2c_transaction_signal is True
    assert probe.evidence["checked_url"] == "https://signal.example"
    assert probe.evidence["http_status"] == 200
    assert "impressum" in probe.evidence["matched_keywords"]["impressum"]
    assert "checkout" in probe.evidence["matched_keywords"]["checkout"]


def test_live_probe_can_use_raw_data_domain_value(db_session: Session) -> None:
    candidate = _create_candidate(
        db_session,
        domain=None,
        raw_data={"website": "raw-domain.example"},
    )

    def fake_fetcher(url: str, settings_: Settings) -> HttpFetchResult:
        return HttpFetchResult(url=url, status_code=200, body=b"Home")

    provider = HttpWebsiteProbeProvider(
        settings_=Settings(website_probe_live_enabled=True),
        fetcher=fake_fetcher,
    )

    probe = run_live_website_probe(db_session, candidate.id, provider=provider)

    assert probe.status.value == "reachable"
    assert probe.url == "https://raw-domain.example"
    assert probe.normalized_domain == "raw-domain.example"


def test_live_website_probe_makes_no_external_network_calls(
    monkeypatch,
    db_session: Session,
) -> None:
    def fail_network(*args, **kwargs):
        raise AssertionError("network access is not allowed in live website probe tests")

    def fake_fetcher(url: str, settings_: Settings) -> HttpFetchResult:
        return HttpFetchResult(url=url, status_code=200, body=b"Shop checkout")

    monkeypatch.setattr(socket, "create_connection", fail_network)
    candidate = _create_candidate(db_session, domain="https://shop.example")
    provider = HttpWebsiteProbeProvider(
        settings_=Settings(website_probe_live_enabled=True),
        fetcher=fake_fetcher,
    )

    probe = run_live_website_probe(db_session, candidate.id, provider=provider)

    assert probe.status.value == "reachable"
    assert probe.has_b2c_transaction_signal is True


def test_live_probe_evidence_has_no_forbidden_legal_claims(
    db_session: Session,
) -> None:
    candidate = _create_candidate(db_session, domain="https://shop.example")

    def fake_fetcher(url: str, settings_: Settings) -> HttpFetchResult:
        return HttpFetchResult(url=url, status_code=200, body=b"Shop checkout")

    provider = HttpWebsiteProbeProvider(
        settings_=Settings(website_probe_live_enabled=True),
        fetcher=fake_fetcher,
    )

    probe = run_live_website_probe(db_session, candidate.id, provider=provider)
    text = json.dumps(probe.evidence, sort_keys=True).casefold()

    assert "legally obligated" not in text
    assert "violation" not in text
    assert "violates" not in text
    assert probe.evidence["no_legal_conclusion"] is True
