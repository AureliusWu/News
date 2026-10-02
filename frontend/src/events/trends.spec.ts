import {describe, expect, it} from "vitest";
import rawPolicy from "../../../backend/config/event_promotions.json";
import {buildTrends, qualityGate, validatePolicy, type TrendPolicy, type PromotionRule} from "./trends";
import type {EventIndex} from "../types/events";
import type {Snapshot} from "../snapshot/transport";

const now = "2026-10-01T12:00:00Z", eid = "e_" + "a".repeat(24);
function fixture(hours = [0], publishers = hours.map(() => "p_one")) {
  const articles = hours.map((h, n) => ({article_id: "a_" + n.toString(16).padStart(24, "0"),
    url: `https://example.org/${n}`, source: {publisher_id: publishers[n]}, published_at: `2026-10-01T${String(12 - h).padStart(2, "0")}:00:00Z`}));
  const binding = {snapshot_id: "b".repeat(24), generated_at: now, content_sha256: "c".repeat(64)};
  return {snapshot: {...binding, articles} as unknown as Snapshot,
    index: {...binding, events: [{event_id: eid, article_ids: articles.map(a => a.article_id)}]} as unknown as EventIndex};
}
const policy = () => JSON.parse(JSON.stringify(rawPolicy)) as TrendPolicy;
function rule(action: "pin" | "exclude" = "pin"): PromotionRule {
  return {rule_id: "synthetic", event_id: eid, action, origin: "maintainer", priority: 10,
    starts_at: "2026-10-01T11:00:00Z", expires_at: "2026-10-01T13:00:00Z", reason: "Synthetic fixture", reference: "test:synthetic"};
}
describe("explainable event activity", () => {
  it("bounds the score at 100 with separate components", () => {
    const f = fixture(Array(8).fill(0), Array.from({length: 8}, (_, n) => "p_" + Math.floor(n / 2)));
    const e = buildTrends(f.index, f.snapshot, policy(), now).events[0];
    expect(e.score).toBe(100); expect(e.components).toEqual({activity: 40, diversity: 40, recency: 20});
  });
  it("caps publisher activity independently of feed volume", () => {
    const f = fixture([0, 0, 0, 0]), e = buildTrends(f.index, f.snapshot, policy(), now).events[0];
    expect(e.score).toBe(40); expect(e.counts.recent_reports).toBe(4); expect(e.counts.recent_capped).toBe(2);
  });
  it("deduplicates tracking links within the same publisher", () => {
    const f = fixture([0, 1]); f.snapshot.articles[0].url = "https://example.org/story?utm_source=one&b=2&a=1#section";
    f.snapshot.articles[1].url = "https://example.org/story?a=1&b=2&fbclid=two";
    const e = buildTrends(f.index, f.snapshot, policy(), now).events[0];
    expect(e.score).toBe(35); expect(e.counts.duplicates_ignored).toBe(1);
  });
  it("uses growth instead of raw article totals", () => {
    const f = fixture([0, 6, 7]), e = buildTrends(f.index, f.snapshot, policy(), now).events[0];
    expect(e.components.activity).toBe(0); expect(e.counts.previous_reports).toBe(2);
  });
  it.each(["invalid", "2026-02-30T00:00:00Z", "2026-10-01T13:00:00Z"])("does not turn missing/future dates into zero: %s", value => {
    const f = fixture(); f.snapshot.articles[0].published_at = value;
    expect(buildTrends(f.index, f.snapshot, policy(), now).events[0].score).toBeNull();
  });
  it("distinguishes valid old activity zero from missing publisher", () => {
    const f = fixture([12]); expect(buildTrends(f.index, f.snapshot, policy(), now).events[0].score).toBe(0);
    delete f.snapshot.articles[0].source.publisher_id;
    expect(buildTrends(f.index, f.snapshot, policy(), now).events[0].score).toBeNull();
  });
  it.each(["pin", "exclude"] as const)("applies %s without changing the score or original evidence", action => {
    const f = fixture(), before = JSON.stringify(f), p = policy(); p.rules = [rule(action)];
    const e = buildTrends(f.index, f.snapshot, p, now).events[0];
    expect(e.score).toBe(35); expect(e.excluded).toBe(action === "exclude"); expect(JSON.stringify(f)).toBe(before);
  });
  it("expires promotion at the actual evaluation clock", () => {
    const f = fixture(), p = policy(); p.rules = [rule()];
    expect(buildTrends(f.index, f.snapshot, p, "2026-10-01T13:00:00Z").events[0].pin).toBeNull();
  });
  it.each(["2026-10-01T14:00:01Z", "2026-10-01T11:54:59Z"])("disables promotions for stale/future data: %s", clock => {
    const f = fixture(), p = policy(); p.rules = [rule()]; const r = buildTrends(f.index, f.snapshot, p, clock);
    expect(r.promotions_enabled).toBe(false); expect(r.events[0].pin).toBeNull(); expect(r.events[0].score).toBe(35);
  });
  it("rejects conflicting, uncited, overlong and changed-formula rules", () => {
    const p = policy(); p.rules = [rule(), {...rule("exclude"), rule_id: "other"}]; expect(() => validatePolicy(p)).toThrow();
    p.rules = [{...rule(), reference: ""}]; expect(() => validatePolicy(p)).toThrow();
    p.rules = [{...rule(), expires_at: "2026-11-01T13:00:00Z"}]; expect(() => validatePolicy(p)).toThrow();
    p.rules = []; p.weights.activity = 50; expect(() => validatePolicy(p)).toThrow();
  });
  it("rejects a foreign generation", () => {
    const f = fixture(); f.index.snapshot_id = "foreign"; expect(() => buildTrends(f.index, f.snapshot, policy(), now)).toThrow("同一版本");
  });
  it("discloses the approved AI provenance and limited denominator", () => {
    expect(qualityGate.sample_pairs).toBe(240); expect(qualityGate.scored_pairs).toBe(238);
    expect(qualityGate.true_positive + qualityGate.false_positive).toBe(15);
    expect(qualityGate.precision).toBe(1); expect(qualityGate.recall).toBe(.5);
    expect(qualityGate.independent_gold).toBe(false); expect(qualityGate.untouched_holdout).toBe(false);
  });
});
