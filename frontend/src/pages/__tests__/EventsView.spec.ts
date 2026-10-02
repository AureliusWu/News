import {afterEach, beforeEach, describe, expect, it, vi} from "vitest";
import {flushPromises, mount, type VueWrapper} from "@vue/test-utils";
import EventsView from "../EventsView.vue";
import type {EventIndex} from "../../types/events";
import type {Snapshot} from "../../snapshot/transport";

const mocked = vi.hoisted(() => ({getEvents: vi.fn(), route: {params: {} as Record<string, string>, query: {q: "bridge", region: "japan", language: "ja"}}}));
vi.mock("../../api/events", () => ({getEvents: mocked.getEvents, resolveEventId: (_i: unknown, id: string) => id}));
vi.mock("vue-router", () => ({useRoute: () => mocked.route}));
vi.mock("../../reading/library", () => ({readingLibrary: {state: {font: "default"}}}));
const first = "e_" + "a".repeat(24), second = "e_" + "b".repeat(24);
function fixture() {
  const now = new Date().toISOString(), time = (h: number) => new Date(Date.parse(now) - h * 3600000).toISOString();
  const source = (id: number) => ({id, slug: `source-${id}`, name: `Source ${id}`, publisher: `Publisher ${id}`, publisher_id: `p_${id}`,
    homepage: "https://example.org", country: "", region: "japan", language: "ja", category: "world", source_type: "official_rss", health_status: "ok", enabled: true});
  const articles = [1, 2, 3, 4].map((id, n) => ({id, article_id: "a_" + String(id).padStart(24, "0"), event_id: n === 0 ? first : second,
    title: n === 0 ? "Latest event" : `Hot report ${id}`, summary: null, url: `https://example.org/${id}`, image_url: null,
    published_at: time(n === 0 ? 1 : n === 1 ? 3 : 2), source: source(n === 0 ? 1 : n), region: "japan", language: "ja", category: "world"}));
  const binding = {snapshot_id: "c".repeat(24), generated_at: now, content_sha256: "d".repeat(64)};
  const events = [first, second].map((id, n) => ({event_id: id, title: n === 0 ? "Latest event" : "Hot event", language: "ja",
    first_published_at: time(n === 0 ? 1 : 3), last_published_at: time(n === 0 ? 1 : 2),
    article_ids: articles.filter(a => a.event_id === id).map(a => a.article_id), publisher_ids: n === 0 ? ["p_1"] : ["p_1", "p_2", "p_3"],
    publisher_count: n === 0 ? 1 : 3, article_count: n === 0 ? 1 : 3, source_names: n === 0 ? ["Source 1"] : ["Source 1", "Source 2", "Source 3"]}));
  return {snapshot: {...binding, articles, sources: [source(1), source(2), source(3)], health: {configured: 3, healthy: 3, failed: 0, gate_pass: true},
    meta: {version: "0.5.0-alpha.1", regions: ["japan"], categories: ["world"], languages: ["ja"], source_count: 3, article_count: 4, last_sync_at: now, publication_mode: "snapshot"}} as Snapshot,
    index: {schema_version: 1, ...binding, events, method_version: "lexical-complete-link-v1", matcher_version: "title-summary-v4", acceptance_status: "ai-evaluation-accepted-with-limitations"} as EventIndex};
}
let wrapper: VueWrapper | undefined;
const render = () => wrapper = mount(EventsView, {global: {stubs: {
  RouterLink: {props: ["to"], template: '<a :data-target="JSON.stringify(to)"><slot /></a>'},
  NewsCard: {props: ["article"], template: '<div class="original">{{article.title}}</div>'}
}}});
beforeEach(() => { mocked.getEvents.mockReset(); mocked.route.params = {}; });
afterEach(() => wrapper?.unmount());
describe("event activity reading", () => {
  it("keeps latest as default, switches to explainable activity and discloses AI limits", async () => {
    mocked.getEvents.mockResolvedValue(fixture()); const w = render(); await flushPromises();
    expect(w.get("select").element.value).toBe("latest"); expect(w.findAll("article")[0].text()).toContain("Latest event");
    await w.get("select").setValue("hot"); expect(w.findAll("article")[0].text()).toContain("Hot event");
    expect(w.text()).toContain("不是独立人工金标"); expect(w.text()).toContain("不代表事实可信度"); expect(w.text()).toContain("快照热度");
  });
  it("keeps unscorable events in latest instead of inventing zero activity", async () => {
    const f = fixture(); f.snapshot.articles.forEach(a => delete a.source.publisher_id);
    mocked.getEvents.mockResolvedValue(f); const w = render(); await flushPromises();
    expect(w.findAll("article")).toHaveLength(2); await w.get("select").setValue("hot"); expect(w.findAll("article")).toHaveLength(0);
    await w.get("select").setValue("latest"); expect(w.findAll("article")).toHaveLength(2);
  });
  it("preserves detail timelines and return filters", async () => {
    mocked.route.params = {eventId: second}; mocked.getEvents.mockResolvedValue(fixture()); const w = render(); await flushPromises();
    expect(w.findAll(".original").map(a => a.text())).toEqual(["Hot report 2", "Hot report 3", "Hot report 4"]);
    expect(w.text()).toContain("机构多样性"); expect(w.findAll("a")[0].attributes("data-target")).toContain("bridge");
  });
  it("shows an actionable load error and supports retry", async () => {
    mocked.getEvents.mockRejectedValueOnce(new Error("offline")).mockResolvedValueOnce(fixture()); const w = render(); await flushPromises();
    expect(w.get('[role="alert"]').text()).toContain("offline"); await w.get("button").trigger("click"); await flushPromises();
    expect(w.findAll("article")).toHaveLength(2); expect(mocked.getEvents).toHaveBeenCalledTimes(2);
  });
});
