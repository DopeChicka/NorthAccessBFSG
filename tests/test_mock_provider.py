import socket

from app.discovery.providers.mock_provider import MockDiscoveryProvider


QUERY_PLAN = [
    {
        "city": "Lübeck",
        "postal_code": "23552",
        "keyword_group_id": "ecommerce",
        "keyword": "online shop",
        "query_text": "Lübeck 23552 online shop",
    },
    {
        "city": "Lübeck",
        "postal_code": "23552",
        "keyword_group_id": "banking",
        "keyword": "bank",
        "query_text": "Lübeck 23552 bank",
    },
]


def test_mock_provider_returns_deterministic_results() -> None:
    provider = MockDiscoveryProvider(max_results=2)

    first = provider.search(QUERY_PLAN)
    second = provider.search(QUERY_PLAN)

    assert first == second
    assert len(first) == 2
    assert first[0].source == "mock"
    assert first[0].source_reference == "mock:luebeck:23552:ecommerce:online-shop"
    assert first[0].company_name == "Mock Candidate Lübeck 23552 Online Shop"
    assert first[0].domain is None
    assert first[0].raw_data == {
        "provider": "mock",
        "mock": True,
        "query_text": "Lübeck 23552 online shop",
        "keyword_group_id": "ecommerce",
        "keyword": "online shop",
    }


def test_mock_provider_makes_no_external_network_calls(monkeypatch) -> None:
    def fail_network(*args, **kwargs):
        raise AssertionError("network access is not allowed in mock provider")

    monkeypatch.setattr(socket, "create_connection", fail_network)

    results = MockDiscoveryProvider(max_results=1).search(QUERY_PLAN)

    assert len(results) == 1
