import copy
import hashlib

import httpx
import pytest

from app.services.event_acceptance import quality_for_matcher, validate_gate
from app.services.event_trends import build_trends, load_policy, validate_policy
from app.services.native_events import _generation

NOW = "2026-10-01T12:00:00Z"
EID = "e_" + "a" * 24


def fixture(hours=(0,), publishers=None):
    publishers = publishers or ["p_one"] * len(hours)
    articles = [{"article_id": "a_" + f"{i:024x}", "url": f"https://example.org/{i}",
                 "source": {"publisher_id": publishers[i]},
                 "published_at": f"2026-10-01T{12 - h:02d}:00:00Z"} for i, h in enumerate(hours)]
    binding = {"snapshot_id": "b" * 24, "generated_at": NOW, "content_sha256": "c" * 64}
    snapshot = {**binding, "articles": articles}
    index = {**binding, "events": [{"event_id": EID, "article_ids": [a["article_id"] for a in articles]}]}
    return index, snapshot


def scored(hours=(0,), publishers=None, policy=None, evaluated_at=NOW):
    i, s = fixture(hours, publishers)
    return build_trends(i, s, policy, evaluated_at=evaluated_at)["events"][0]


def rule(action="pin"):
    return {"rule_id": "test_rule", "event_id": EID, "action": action, "origin": "maintainer",
            "priority": 10, "starts_at": "2026-10-01T11:00:00Z", "expires_at": "2026-10-01T13:00:00Z",
            "reason": "Synthetic acceptance fixture", "reference": "test:synthetic"}


def test_maximum_is_100_and_components_are_explainable():
    result = scored([0] * 8, [f"p_{i // 2}" for i in range(8)])
    assert result["score"] == 100
    assert result["components"] == {"activity": 40, "diversity": 40, "recency": 20}


def test_publisher_cap_is_not_feed_count():
    result = scored([0, 0, 0, 0])
    assert result["counts"]["recent_reports"] == 4
    assert result["counts"]["recent_capped"] == 2
    assert result["counts"]["recent_publishers"] == 1
    assert result["score"] == 40


def test_tracking_and_fragment_duplicate_same_publisher():
    i, s = fixture([0, 1])
    s["articles"][0]["url"] = "https://example.org/story?utm_source=one&b=2&a=1#section"
    s["articles"][1]["url"] = "https://example.org/story?a=1&b=2&fbclid=two"
    result = build_trends(i, s, evaluated_at=NOW)["events"][0]
    assert result["counts"]["duplicates_ignored"] == 1
    assert result["counts"]["recent_reports"] == 1
    assert result["score"] == 35


def test_different_publishers_are_not_collapsed_and_independence_is_not_claimed():
    i, s = fixture([0, 0], ["p_one", "p_two"])
    s["articles"][1]["url"] = s["articles"][0]["url"]
    result = build_trends(i, s, evaluated_at=NOW)["events"][0]
    assert result["counts"]["recent_publishers"] == 2
    assert result["score"] == 50


def test_growth_uses_previous_window_and_boundary_belongs_to_previous():
    result = scored([0, 6, 7])
    assert result["counts"]["previous_reports"] == 2
    assert result["components"]["activity"] == 0
    assert result["score"] == 30


def test_old_valid_evidence_is_zero_not_missing():
    assert scored([12])["score"] == 0
    assert scored([12])["hot_eligible"] is False


@pytest.mark.parametrize("field,value", [("published_at", "invalid"), ("published_at", "2026-02-30T00:00:00Z"),
                                        ("published_at", "2026-10-01T13:00:00Z"), ("url", "javascript:alert(1)")])
def test_invalid_or_future_only_evidence_is_null(field, value):
    i, s = fixture()
    s["articles"][0][field] = value
    result = build_trends(i, s, evaluated_at=NOW)["events"][0]
    assert result["score"] is None and result["components"]["recency"] is None


def test_missing_publisher_is_not_zero_or_an_extra_publisher():
    i, s = fixture()
    s["articles"][0]["source"] = {}
    result = build_trends(i, s, evaluated_at=NOW)["events"][0]
    assert result["score"] is None and result["counts"]["invalid_ignored"] == 1


@pytest.mark.parametrize("field", ["snapshot_id", "generated_at", "content_sha256"])
def test_cross_generation_is_rejected(field):
    i, s = fixture()
    i[field] = "foreign"
    with pytest.raises(ValueError, match="same valid snapshot"):
        build_trends(i, s, evaluated_at=NOW)


@pytest.mark.parametrize("action", ["pin", "exclude"])
def test_explicit_rules_do_not_mutate_data_or_numeric_score(action):
    i, s = fixture()
    before = copy.deepcopy((i, s))
    policy = load_policy()
    policy["rules"] = [rule(action)]
    result = build_trends(i, s, policy, evaluated_at=NOW)["events"][0]
    assert (i, s) == before and result["score"] == 35
    assert result["excluded"] is (action == "exclude")
    assert result["hot_eligible"] is (action == "pin")
    assert (result["pin"] if action == "pin" else result["exclusion"])["reference"] == "test:synthetic"


def test_expiry_uses_current_clock_not_captured_snapshot_clock():
    policy = load_policy()
    policy["rules"] = [rule()]
    result = scored(policy=policy, evaluated_at="2026-10-01T13:00:00Z")
    assert result["pin"] is None


@pytest.mark.parametrize("clock,reason", [("2026-10-01T14:00:01Z", "stale-snapshot"),
                                        ("2026-10-01T11:54:59Z", "future-snapshot")])
def test_stale_and_future_snapshots_disable_promotions(clock, reason):
    i, s = fixture()
    policy = load_policy()
    policy["rules"] = [rule()]
    report = build_trends(i, s, policy, evaluated_at=clock)
    assert report["promotion_disabled_reason"] == reason
    assert report["events"][0]["pin"] is None and report["events"][0]["score"] == 35


@pytest.mark.parametrize("field,value", [("priority", -1), ("priority", 101), ("priority", True),
                                        ("origin", "human-gold"), ("reason", ""), ("reference", ""),
                                        ("expires_at", "2026-11-01T13:00:00Z"), ("starts_at", "2026-10-01T11:00:00")])
def test_invalid_rules_are_rejected(field, value):
    policy = load_policy()
    r = rule()
    r[field] = value
    policy["rules"] = [r]
    with pytest.raises(ValueError):
        validate_policy(policy)


def test_conflicting_rules_and_changed_formula_are_rejected():
    policy = load_policy()
    policy["rules"] = [rule(), {**rule("exclude"), "rule_id": "other"}]
    with pytest.raises(ValueError):
        validate_policy(policy)
    policy["rules"] = []
    policy["weights"]["activity"] = 50
    with pytest.raises(ValueError):
        validate_policy(policy)


def test_user_approved_ai_gate_is_honest_and_version_bound():
    gate = quality_for_matcher("title-summary-v4")
    assert gate["sample_pairs"] == 240 and gate["scored_pairs"] == 238
    assert gate["precision"] == 1 and gate["recall"] == .5
    assert gate["independent_gold"] is False and gate["untouched_holdout"] is False
    assert quality_for_matcher("future-unreviewed-matcher")["acceptance_status"] == "review-required"
    with pytest.raises(ValueError):
        validate_gate({**gate, "independent_gold": True})
    with pytest.raises(ValueError):
        validate_gate({**gate, "recall": 1})


def test_native_generation_version_binding_preserves_legacy_reader():
    news = {"generated_at": NOW, "content_sha256": "c" * 64, "meta": {"version": "0.4.0-alpha.1"}}
    legacy = hashlib.sha256((NOW + ":" + "c" * 64).encode()).hexdigest()[:24]
    assert _generation(news) == legacy
    news["generation_method"] = "native-version-bound-v1"
    old = _generation(news)
    news["meta"]["version"] = "0.5.0-alpha.1"
    assert _generation(news) != old


@pytest.mark.asyncio
async def test_trends_route_is_prefixed_and_bound_to_native_bundle(monkeypatch):
    from app.api.routes import trends
    from app.core.db import get_db
    from app.main import app
    i, s = fixture()
    async def bundle(_db):
        return {"events": i, "news": s}
    async def database():
        yield object()
    monkeypatch.setattr(trends, "native_bundle", bundle)
    app.dependency_overrides[get_db] = database
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            result = await client.get("/api/v1/trends")
            assert result.status_code == 200 and result.json()["snapshot_id"] == s["snapshot_id"]
            assert (await client.get("/trends")).status_code == 404
            def broken(*args, **kwargs):
                raise ValueError("bad policy")
            monkeypatch.setattr(trends, "build_trends", broken)
            result = await client.get("/api/v1/trends")
            assert result.status_code == 503 and result.headers["Retry-After"] == "5"
    finally:
        app.dependency_overrides.pop(get_db, None)
