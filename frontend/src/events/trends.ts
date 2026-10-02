import rawPolicy from "../../../backend/config/event_promotions.json";
import rawGate from "../../../backend/config/event_quality_gate.json";
import type {EventIndex} from "../types/events";
import type {Snapshot} from "../snapshot/transport";

export interface PromotionRule {
  rule_id: string; event_id: string; action: "pin" | "exclude"; origin: "maintainer" | "ai-reviewed";
  priority: number; starts_at: string; expires_at: string; reason: string; reference: string;
}
export interface TrendPolicy {
  schema_version: number; method_version: string; policy_version: string; window_hours: number;
  per_publisher_cap: number; max_promotion_age_hours: number;
  weights: {activity: number; diversity: number; recency: number}; rules: PromotionRule[];
}
type Promotion = Omit<PromotionRule, "event_id" | "action" | "starts_at">;
export interface EventTrend {
  event_id: string; score: number | null; status: "scored" | "unscored"; unscored_reason: string | null;
  components: {activity: number | null; diversity: number | null; recency: number | null};
  counts: {recent_reports: number; previous_reports: number; recent_publishers: number;
    recent_capped: number; previous_capped: number; duplicates_ignored: number; invalid_ignored: number; future_ignored: number};
  pin: Promotion | null; excluded: boolean; exclusion: Promotion | null; hot_eligible: boolean;
}
export interface TrendReport {
  schema_version: number; snapshot_id: string; generated_at: string; content_sha256: string; as_of: string;
  method_version: string; policy_version: string; rule_evaluated_at: string;
  promotions_enabled: boolean; promotion_disabled_reason: string | null; events: EventTrend[];
}
export const qualityGate = rawGate;
const method = "recent-publisher-activity-v1";
const iso = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})$/;
function instant(value: unknown): number | null {
  if (typeof value !== "string" || !iso.test(value)) return null;
  const y = Number(value.slice(0, 4)), m = Number(value.slice(5, 7)), d = Number(value.slice(8, 10));
  const days = new Date(Date.UTC(y, m, 0)).getUTCDate();
  if (m < 1 || m > 12 || d < 1 || d > days || Number(value.slice(11, 13)) > 23
    || Number(value.slice(14, 16)) > 59 || Number(value.slice(17, 19)) > 59) return null;
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) ? parsed / 1000 : null;
}
export function validatePolicy(value: unknown): TrendPolicy {
  const p = value as TrendPolicy;
  if (!p || p.schema_version !== 1 || p.method_version !== method || p.window_hours !== 6
    || p.per_publisher_cap !== 2 || p.max_promotion_age_hours !== 2
    || p.weights?.activity !== 40 || p.weights.diversity !== 40 || p.weights.recency !== 20
    || typeof p.policy_version !== "string" || !p.policy_version || !Array.isArray(p.rules) || p.rules.length > 100
    || new TextEncoder().encode(JSON.stringify(p)).length > 65536) throw new Error("热度规则配置无效");
  const ids = new Set<string>(), events = new Set<string>();
  for (const r of p.rules) {
    if (!r || typeof r !== "object") throw new Error("推荐规则配置无效");
    const start = instant(r.starts_at), end = instant(r.expires_at);
    if (typeof r.rule_id !== "string" || !/^[a-zA-Z0-9_-]{1,64}$/.test(r.rule_id)
      || typeof r.event_id !== "string" || !/^e_[a-f0-9]{24}$/.test(r.event_id)
      || ids.has(r.rule_id) || events.has(r.event_id) || !["pin", "exclude"].includes(r.action)
      || !["maintainer", "ai-reviewed"].includes(r.origin) || !Number.isInteger(r.priority) || r.priority < 0 || r.priority > 100
      || start === null || end === null || end <= start || end - start > 7 * 86400
      || [r.reason, r.reference].some(s => typeof s !== "string" || !s.trim() || [...s].length > 240))
      throw new Error("推荐规则无效或互相冲突");
    ids.add(r.rule_id); events.add(r.event_id);
  }
  return p;
}
function canonicalUrl(value: unknown): string | null {
  if (typeof value !== "string") return null;
  value = value.trim();
  try { const u = new URL(value as string); if (!["http:", "https:"].includes(u.protocol) || !u.hostname || u.username || u.password) return null; }
  catch { return null; }
  const [head, ...tail] = (value as string).split("#")[0].split("?");
  const retained = tail.join("?").split("&").filter(part => {
    const key = part.split("=")[0].toLowerCase(); return part && !key.startsWith("utm_") && !["fbclid", "gclid"].includes(key);
  }).sort();
  return head + (retained.length ? "?" + retained.join("&") : "");
}
const rounded = (n: number) => Math.floor(n * 10 + 0.5) / 10;
export function buildTrends(index: EventIndex, snapshot: Snapshot, policy: unknown = rawPolicy,
  evaluatedAt = new Date().toISOString()): TrendReport {
  const p = validatePolicy(policy), asOf = instant(snapshot.generated_at), now = instant(evaluatedAt);
  if (asOf === null || ["snapshot_id", "generated_at", "content_sha256"].some(k =>
    index[k as keyof EventIndex] !== snapshot[k as keyof Snapshot])) throw new Error("热度报告与新闻快照不属于同一版本");
  if (now === null) throw new Error("规则评估时间无效");
  const disabled = now - asOf > 7200 ? "stale-snapshot" : now - asOf < -300 ? "future-snapshot" : null;
  const articles = new Map(snapshot.articles.map(a => [a.article_id, a]));
  const events: EventTrend[] = index.events.map(event => {
    const evidence = new Map<string, {publisher: string; published: number}>();
    let invalid = 0, future = 0, duplicates = 0;
    for (const aid of event.article_ids) {
      const a = articles.get(aid), publisher = a?.source.publisher_id, published = instant(a?.published_at), url = canonicalUrl(a?.url);
      if (typeof publisher !== "string" || !publisher.trim() || published === null || url === null) { invalid++; continue; }
      if (published > asOf) { future++; continue; }
      const key = JSON.stringify([publisher, url]), old = evidence.get(key);
      if (old) duplicates++;
      evidence.set(key, {publisher, published: Math.max(published, old?.published ?? published)});
    }
    const recent = new Map<string, number>(), previous = new Map<string, number>();
    for (const {publisher, published} of evidence.values()) {
      const target = published > asOf - 21600 ? recent : published > asOf - 43200 ? previous : null;
      if (target) target.set(publisher, (target.get(publisher) || 0) + 1);
    }
    const sum = (map: Map<string, number>, cap = Infinity) => [...map.values()].reduce((a, v) => a + Math.min(v, cap), 0);
    const rc = sum(recent, 2), pc = sum(previous, 2);
    let parts: EventTrend["components"] = {activity: null, diversity: null, recency: null}, score: number | null = null;
    if (evidence.size) {
      const newest = Math.max(...[...evidence.values()].map(a => a.published));
      parts = {activity: rounded(Math.min(Math.max(rc - pc, 0) / 8, 1) * 40),
        diversity: rounded(Math.min(recent.size / 4, 1) * 40), recency: rounded(Math.max(0, 1 - (asOf - newest) / 21600) * 20)};
      score = rounded((parts.activity ?? 0) + (parts.diversity ?? 0) + (parts.recency ?? 0));
    }
    const rule = disabled === null ? p.rules.find(r => r.event_id === event.event_id && instant(r.starts_at)! <= now && now < instant(r.expires_at)!) : undefined;
    const promotion: Promotion | null = rule ? {rule_id: rule.rule_id, origin: rule.origin, priority: rule.priority,
      reason: rule.reason, reference: rule.reference, expires_at: rule.expires_at} : null;
    const pin = rule?.action === "pin" ? promotion : null, exclusion = rule?.action === "exclude" ? promotion : null;
    return {event_id: event.event_id, score, status: score === null ? "unscored" : "scored",
      unscored_reason: score === null ? "no-valid-publication-evidence" : null, components: parts,
      counts: {recent_reports: sum(recent), previous_reports: sum(previous), recent_publishers: recent.size,
        recent_capped: rc, previous_capped: pc, duplicates_ignored: duplicates, invalid_ignored: invalid, future_ignored: future},
      pin, excluded: exclusion !== null, exclusion, hot_eligible: score !== null && (score > 0 || pin !== null) && exclusion === null};
  });
  return {schema_version: 1, snapshot_id: snapshot.snapshot_id!, generated_at: snapshot.generated_at,
    content_sha256: snapshot.content_sha256!, as_of: snapshot.generated_at, method_version: method,
    policy_version: p.policy_version, rule_evaluated_at: evaluatedAt, promotions_enabled: disabled === null,
    promotion_disabled_reason: disabled, events};
}
