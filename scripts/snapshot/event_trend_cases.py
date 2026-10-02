"""Synthetic cross-runtime fixtures. No network, labels or real news writes."""
import copy
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
from app.services.event_trends import build_trends, load_policy

NOW = "2026-10-01T12:00:00Z"
EID = "e_" + "a" * 24


def fixture(hours=(0,), publishers=None):
    publishers = publishers or ["p_one"] * len(hours)
    instant = datetime(2026, 10, 1, 12, tzinfo=timezone.utc)
    articles = [{"id": i + 1, "article_id": "a_" + f"{i:024x}", "event_id": EID,
                 "title": f"Synthetic report {i}", "summary": None, "image_url": None,
                 "url": f"https://example.org/{i}", "source": {"publisher_id": publishers[i]},
                 "published_at": (instant - timedelta(hours=h)).isoformat().replace("+00:00", "Z")}
                for i, h in enumerate(hours)]
    binding = {"snapshot_id": "b" * 24, "generated_at": NOW, "content_sha256": "c" * 64}
    return {"name": "base", "snapshot": {**binding, "articles": articles},
            "index": {**binding, "events": [{"event_id": EID, "article_ids": [a["article_id"] for a in articles]}]},
            "policy": load_policy(), "evaluated_at": NOW}


def fixtures():
    cases = []
    for name, hours, pubs in [("one-publisher", [0, 0, 0, 0], None),
                              ("maximum", [0] * 8, [f"p_{i // 2}" for i in range(8)]),
                              ("previous-boundary", [0, 6, 7, 12], None),
                              ("fractional-recency", [1.25, 2.5], ["p_one", "p_two"]),
                              ("old-zero", [24], None)]:
        c = fixture(hours, pubs)
        c["name"] = name
        cases.append(c)
    for name in ("tracked-url", "missing-publisher", "invalid-date", "future-publication", "pin", "exclude", "expired", "stale-snapshot", "future-snapshot"):
        c = fixture([0, 1] if name == "tracked-url" else [0])
        c["name"] = name
        if name == "tracked-url":
            c["snapshot"]["articles"][0]["url"] = "https://example.org/story?b=2&utm_source=one&a=1#section"
            c["snapshot"]["articles"][1]["url"] = "https://example.org/story?a=1&fbclid=two&b=2"
        if name == "missing-publisher":
            c["snapshot"]["articles"][0]["source"] = {}
        if name in ("invalid-date", "future-publication"):
            c["snapshot"]["articles"][0]["published_at"] = "invalid" if name == "invalid-date" else "2026-10-01T13:00:00Z"
        if name in ("pin", "exclude", "expired", "stale-snapshot", "future-snapshot"):
            c["policy"]["rules"] = [{"rule_id": "synthetic", "event_id": EID,
                                     "action": "exclude" if name == "exclude" else "pin", "origin": "ai-reviewed", "priority": 10,
                                     "starts_at": "2026-10-01T11:00:00Z", "expires_at": "2026-10-01T13:00:00Z",
                                     "reason": "Synthetic acceptance only", "reference": "test:synthetic"}]
        c["evaluated_at"] = {"expired": "2026-10-01T13:00:00Z", "stale-snapshot": "2026-10-01T14:00:01Z",
                             "future-snapshot": "2026-10-01T11:54:59Z"}.get(name, NOW)
        cases.append(c)
    for c in cases:
        c["expected"] = build_trends(c["index"], c["snapshot"], c["policy"], evaluated_at=c["evaluated_at"])
    return cases


if __name__ == "__main__":
    print(json.dumps(fixtures(), ensure_ascii=True))
