import {afterEach, describe, expect, it, vi} from "vitest";
import {ApiProvider, createSnapshotProvider} from "./providers";
import {validateEventIndex, resolveEventId} from "./events";
import type {Snapshot} from "../snapshot/transport";

const generation = "a".repeat(24), eventId = "e_" + "b".repeat(24), articleId = "a_" + "c".repeat(24), publisherId = "p_" + "d".repeat(20);
function fixture(): Snapshot {
  const now = new Date(Date.now() - 60000).toISOString();
  const source = {id: 1, slug: "one", name: "One", publisher: "Publisher", publisher_id: publisherId,
    homepage: "https://example.org", country: "", region: "world", language: "en", category: "world", source_type: "official_rss", health_status: "ok", enabled: true};
  return {schema_version: 1, snapshot_id: generation, generated_at: now, content_sha256: "e".repeat(64),
    events_file: `events.${generation}.json`, source_health_file: `source-health.${generation}.json`, sources: [source],
    articles: [{id: 1, article_id: articleId, event_id: eventId, title: "One headline", summary: null, source,
      url: "https://example.org/one", image_url: null, published_at: now, region: "world", category: "world", language: "en"}],
    health: {configured: 1, healthy: 1, failed: 0, gate_pass: true},
    meta: {version: "0.4.0-alpha.1", regions: ["world"], categories: ["world"], languages: ["en"], source_count: 1, article_count: 1, last_sync_at: now, publication_mode: "snapshot"}};
}
function report(s: Snapshot) {
  return {schema_version: 1, snapshot_id: s.snapshot_id, content_sha256: s.content_sha256, generated_at: s.generated_at,
    method_version: "lexical-complete-link-v1", acceptance_status: "awaiting-human-evaluation", events: [{event_id: eventId,
      title: "One headline", language: "en", first_published_at: s.generated_at, last_published_at: s.generated_at,
      article_ids: [articleId], article_count: 1, publisher_ids: [publisherId], publisher_count: 1, source_names: ["One"]}]};
}
const json = (data: unknown) => new Response(JSON.stringify(data), {headers: {"content-type": "application/json"}});
afterEach(() => vi.unstubAllGlobals());
describe("explicit providers", () => {
  it("keeps API origin separate and validates response MIME", async () => {
    const mocked = vi.fn(async (_input: RequestInfo | URL, _init?: RequestInit) => json({items: [], has_more: false, next_cursor: null})); vi.stubGlobal("fetch", mocked);
    await new ApiProvider("https://api.example.org").request("news");
    expect(mocked.mock.calls[0][0]).toBe("https://api.example.org/api/v1/news");
    vi.stubGlobal("fetch", vi.fn(async () => new Response("<html>")));
    await expect(new ApiProvider().request("news")).rejects.toThrow("invalid response");
  });
  it("uses the same snapshot for news and event references without changing global fetch", async () => {
    const before = globalThis.fetch, s = fixture();
    const network = vi.fn(async (url: RequestInfo | URL) => json(String(url).endsWith("news.json") ? s : report(s)));
    const provider = createSnapshotProvider(network as typeof fetch, {origin: "https://example.org", basePath: "/News/"});
    const snapshot = await provider.snapshot();
    const page = await (await provider.request("news?limit=30")).json();
    const index = validateEventIndex(await provider.asset(snapshot, snapshot.events_file!), snapshot);
    expect(index.events[0].article_ids).toEqual([page.items[0].article_id]);
    expect(network).toHaveBeenCalledTimes(2); expect(globalThis.fetch).toBe(before);
  });
  it("refuses traversal, external files and cross-generation assets", async () => {
    const s = fixture(); const provider = createSnapshotProvider(vi.fn(), {origin: "https://example.org", basePath: "/News/"});
    for (const name of ["../secret.json", "https://other.example.org/report.json", "events." + "f".repeat(24) + ".json"])
      await expect(provider.asset(s, name)).rejects.toThrow("版本化报告");
  });
  it("rejects a response from a different generation", async () => {
    const s = fixture(); const network = vi.fn(async () => json({...report(s), snapshot_id: "f".repeat(24)}));
    const provider = createSnapshotProvider(network as typeof fetch, {origin: "https://example.org", basePath: "/News/"});
    await expect(provider.asset(s, s.events_file!)).rejects.toThrow("同一版本");
  });
  it("does not search missing summaries as the literal word null", async () => {
    const s = fixture(); const provider = createSnapshotProvider(vi.fn(async () => json(s)), {origin: "https://example.org", basePath: "/News/"});
    expect((await (await provider.request("news?q=null")).json()).items).toEqual([]);
  });
  it("uses native API snapshots and immutable reports without a Pages fallback", async () => {
    const s = fixture(); const mocked = vi.fn(async (url: RequestInfo | URL) => json(String(url).endsWith("/snapshot") ? s : report(s)));
    vi.stubGlobal("fetch", mocked);
    const provider = new ApiProvider("https://api.example.org");
    const snapshot = await provider.snapshot();
    expect(validateEventIndex(await provider.asset(snapshot, s.events_file!), snapshot).events).toHaveLength(1);
    expect(mocked.mock.calls.map(call => call[0])).toEqual(["https://api.example.org/api/v1/snapshot", `https://api.example.org/api/v1/snapshots/${generation}/${s.events_file}`]);
  });
  it("reports an unconfigured native API instead of disguising it as a snapshot", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({detail: "unconfigured"}), {status: 503, headers: {"content-type": "application/json"}})));
    await expect(new ApiProvider().snapshot()).rejects.toThrow("HTTP 503");
  });
  it("rejects unsafe native report paths before requesting them", async () => {
    const mocked = vi.fn(); vi.stubGlobal("fetch", mocked); const provider = new ApiProvider(); const s = fixture();
    for (const name of ["../private.json", "https://other.example.org/data.json", "events." + "f".repeat(24) + ".json"])
      await expect(provider.asset(s, name)).rejects.toThrow("版本化报告");
    expect(mocked).not.toHaveBeenCalled();
  });
  it("requires every native report binding and enforces its bound", async () => {
    const s = fixture(); const provider = new ApiProvider();
    for (const changed of [{...report(s), snapshot_id: "f".repeat(24)}, {...report(s), generated_at: undefined}, {...report(s), content_sha256: undefined}]) {
      vi.stubGlobal("fetch", vi.fn(async () => json(changed)));
      await expect(provider.asset(s, s.events_file!)).rejects.toThrow("同一版本");
    }
    vi.stubGlobal("fetch", vi.fn(async () => new Response("x".repeat(4 * 1024 * 1024 + 1), {headers: {"content-type": "application/json"}})));
    await expect(provider.asset(s, s.events_file!)).rejects.toThrow("大小限制");
  });
});
describe("event evidence validation", () => {
  it("resolves validated retired event URLs without changing current IDs", () => {
    const s = fixture(), old = "e_" + "a".repeat(24);
    const index = validateEventIndex({...report(s), aliases: {[old]: eventId}}, s);
    expect(resolveEventId(index, old)).toBe(eventId);
    expect(resolveEventId(index, eventId)).toBe(eventId);
    expect(resolveEventId(index, "__proto__")).toBe("__proto__");
  });
  it("rejects alias cycles, foreign targets and active-ID replacement", () => {
    const s = fixture(), old = "e_" + "a".repeat(24);
    for (const aliases of [{[old]: old}, {[old]: "e_" + "f".repeat(24)}, {[eventId]: eventId}])
      expect(() => validateEventIndex({...report(s), aliases}, s)).toThrow("历史链接");
  });
  it("accepts consistent evidence", () => { const s = fixture(); expect(validateEventIndex(report(s), s).events).toHaveLength(1); });
  it("rejects inflated publisher counts", () => {
    const s = fixture(), r = report(s); r.events[0].publisher_count = 2;
    expect(() => validateEventIndex(r, s)).toThrow();
  });
  it("rejects foreign article references and incomplete coverage", () => {
    const s = fixture(), r = report(s); r.events[0].article_ids = ["foreign"];
    expect(() => validateEventIndex(r, s)).toThrow();
    expect(() => validateEventIndex({...report(s), events: []}, s)).toThrow("未覆盖");
  });
});
