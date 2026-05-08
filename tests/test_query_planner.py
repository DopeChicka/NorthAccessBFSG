import socket

from app.discovery.query_planner import build_query_plan, get_enabled_keyword_groups


def test_query_planner_returns_deterministic_plan_for_luebeck() -> None:
    first = build_query_plan("Lübeck")
    second = build_query_plan("Luebeck")

    assert first.postal_codes == second.postal_codes
    assert first.query_plan == second.query_plan
    assert first.city == "Lübeck"
    assert first.query_plan[0] == {
        "city": "Lübeck",
        "postal_code": first.postal_codes[0],
        "keyword_group_id": "ecommerce",
        "keyword": "online shop",
        "query_text": f"Lübeck {first.postal_codes[0]} online shop",
    }


def test_query_plan_uses_postal_codes_and_enabled_keyword_groups() -> None:
    plan = build_query_plan("lubeck")
    enabled_groups = get_enabled_keyword_groups()
    enabled_keywords_count = sum(len(group["keywords"]) for group in enabled_groups)

    assert plan.postal_codes
    assert all(entry["postal_code"] in plan.postal_codes for entry in plan.query_plan)
    assert len(plan.query_plan) == len(plan.postal_codes) * enabled_keywords_count
    assert {entry["keyword_group_id"] for entry in plan.query_plan} == {
        str(group["group_id"]) for group in enabled_groups
    }


def test_query_planner_makes_no_external_network_calls(monkeypatch) -> None:
    def fail_network(*args, **kwargs):
        raise AssertionError("network access is not allowed in query planner")

    monkeypatch.setattr(socket, "create_connection", fail_network)

    plan = build_query_plan("Lübeck")

    assert plan.query_plan
