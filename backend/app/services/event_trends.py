"""Deterministic snapshot-time activity, not truth or source credibility."""
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

POLICY_PATH = Path(__file__).resolve().parents[2] / "config" / "event_promotions.json"
METHOD = "recent-publisher-activity-v1"
ISO = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})$")


def instant(value):
    if not isinstance(value, str) or not ISO.fullmatch(value):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except (ValueError, OverflowError):
        return None


def validate_policy(policy: dict) -> dict:
    if (not isinstance(policy, dict) or policy.get("schema_version") != 1
            or policy.get("method_version") != METHOD or policy.get("window_hours") != 6
            or policy.get("per_publisher_cap") != 2 or policy.get("max_promotion_age_hours") != 2
            or policy.get("weights") != {"activity": 40, "diversity": 40, "recency": 20}
            or not isinstance(policy.get("policy_version"), str) or not policy["policy_version"]
            or not isinstance(policy.get("rules"), list) or len(policy["rules"]) > 100
            or len(json.dumps(policy, ensure_ascii=False).encode("utf-8")) > 65536):
        raise ValueError("Invalid event promotion policy")
    ids, events = set(), set()
    for rule in policy["rules"]:
        if not isinstance(rule, dict):
            raise ValueError("Invalid promotion rule")
        start, end = instant(rule.get("starts_at")), instant(rule.get("expires_at"))
        rid, eid = rule.get("rule_id"), rule.get("event_id")
        if (not isinstance(rid, str) or not re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", rid)
                or not isinstance(eid, str) or not re.fullmatch(r"e_[a-f0-9]{24}", eid)
                or rid in ids or eid in events or rule.get("action") not in ("pin", "exclude")
                or rule.get("origin") not in ("maintainer", "ai-reviewed")
                or type(rule.get("priority")) is not int or not 0 <= rule["priority"] <= 100
                or start is None or end is None or not 0 < end - start <= 7 * 86400
                or any(not isinstance(rule.get(k), str) or not rule[k].strip() or len(rule[k]) > 240 for k in ("reason", "reference"))):
            raise ValueError("Invalid or conflicting promotion rule")
        ids.add(rid)
        events.add(eid)
    return policy


def load_policy() -> dict:
    with POLICY_PATH.open("rb") as stream:
        raw = stream.read(65537)
    if len(raw) > 65536:
        raise ValueError("Event promotion policy too large")
    return validate_policy(json.loads(raw))


def canonical_url(value):
    """Deduplicate normalized feed URLs; strip fragment and common tracking keys."""
    if not isinstance(value, str):
        return None
    value = value.strip()
    try:
        parsed = urlsplit(value)
        if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password:
            return None
    except ValueError:
        return None
    head, _, query = value.split("#", 1)[0].partition("?")
    retained = sorted(part for part in query.split("&") if part and not (
        part.split("=", 1)[0].lower().startswith("utm_") or part.split("=", 1)[0].lower() in ("fbclid", "gclid")))
    return head + ("?" + "&".join(retained) if retained else "")


def rounded(value: float) -> float:
    return math.floor(value * 10 + 0.5) / 10


def build_trends(index: dict, snapshot: dict, policy: dict | None = None, *, evaluated_at: str | None = None) -> dict:
    policy = validate_policy(policy) if policy is not None else load_policy()
    as_of = instant(snapshot.get("generated_at"))
    if as_of is None or any(index.get(k) != snapshot.get(k) for k in ("snapshot_id", "generated_at", "content_sha256")):
        raise ValueError("Event trends require the same valid snapshot generation")
    evaluated_at = evaluated_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    now = instant(evaluated_at)
    if now is None:
        raise ValueError("Invalid promotion evaluation time")
    age = now - as_of
    disabled = "stale-snapshot" if age > 7200 else "future-snapshot" if age < -300 else None
    articles = {a.get("article_id"): a for a in snapshot["articles"]}
    output = []
    for event in index["events"]:
        evidence = {}
        invalid = future = duplicates = 0
        for aid in event["article_ids"]:
            article = articles.get(aid)
            publisher = article.get("source", {}).get("publisher_id") if article else None
            published = instant(article.get("published_at")) if article else None
            url = canonical_url(article.get("url")) if article else None
            if not isinstance(publisher, str) or not publisher.strip() or published is None or url is None:
                invalid += 1
                continue
            if published > as_of:
                future += 1
                continue
            key = (publisher, url)
            if key in evidence:
                duplicates += 1
            evidence[key] = max(published, evidence.get(key, published))
        recent, previous = {}, {}
        for (publisher, _), published in evidence.items():
            target = recent if published > as_of - 21600 else previous if published > as_of - 43200 else None
            if target is not None:
                target[publisher] = target.get(publisher, 0) + 1
        rc = sum(min(v, 2) for v in recent.values())
        pc = sum(min(v, 2) for v in previous.values())
        parts = {"activity": None, "diversity": None, "recency": None}
        score = None
        if evidence:
            parts = {"activity": rounded(min(max(rc - pc, 0) / 8, 1) * 40),
                     "diversity": rounded(min(len(recent) / 4, 1) * 40),
                     "recency": rounded(max(0, 1 - (as_of - max(evidence.values())) / 21600) * 20)}
            score = rounded(sum(parts.values()))
        rule = next((r for r in policy["rules"] if r["event_id"] == event["event_id"]
                     and instant(r["starts_at"]) <= now < instant(r["expires_at"])), None) if disabled is None else None
        promotion = {k: rule[k] for k in ("rule_id", "origin", "priority", "reason", "reference", "expires_at")} if rule else None
        pin = promotion if rule and rule["action"] == "pin" else None
        exclusion = promotion if rule and rule["action"] == "exclude" else None
        output.append({"event_id": event["event_id"], "score": score,
                       "status": "scored" if score is not None else "unscored",
                       "unscored_reason": None if score is not None else "no-valid-publication-evidence",
                       "components": parts,
                       "counts": {"recent_reports": sum(recent.values()), "previous_reports": sum(previous.values()),
                                  "recent_publishers": len(recent), "recent_capped": rc, "previous_capped": pc,
                                  "duplicates_ignored": duplicates, "invalid_ignored": invalid, "future_ignored": future},
                       "pin": pin, "excluded": exclusion is not None, "exclusion": exclusion,
                       "hot_eligible": score is not None and (score > 0 or pin is not None) and exclusion is None})
    return {"schema_version": 1, **{k: snapshot[k] for k in ("snapshot_id", "generated_at", "content_sha256")},
            "as_of": snapshot["generated_at"], "method_version": METHOD, "policy_version": policy["policy_version"],
            "rule_evaluated_at": evaluated_at, "promotions_enabled": disabled is None,
            "promotion_disabled_reason": disabled, "events": output}
