import {afterEach, beforeEach, describe, expect, it, vi} from "vitest";
import {flushPromises, mount, type VueWrapper} from "@vue/test-utils";
import HomeView from "../HomeView.vue";
import NewsCard from "../../components/NewsCard.vue";
import {formatRelativeTime} from "../../utils/time";
import type {NewsArticle} from "../../types/news";

const source = {id: 1, slug: "test-source", name: "Example Publisher", publisher: "Example", homepage: "https://example.org", country: "GB", region: "world", language: "en", category: "world", source_type: "official_rss", health_status: "ok", enabled: true};
const article = (id = 1, fields: Partial<NewsArticle> = {}): NewsArticle => ({
  id, title: "A real headline " + id, summary: "A short readable excerpt.", url: "https://example.org/story/" + id,
  image_url: null, published_at: new Date(Date.now() - 180000).toISOString(),
  source, region: "world", category: "world", language: "en", ...fields
});
const page = (items = [article()], next: string | null = null) => ({items, next_cursor: next, has_more: next !== null});
const json = (body: unknown, headers = {}) => new Response(JSON.stringify(body), {headers: {"content-type": "application/json", ...headers}});
let wrapper: VueWrapper | undefined;
let news: (url: string) => Promise<Response>;
let fetchMock: ReturnType<typeof vi.fn>;
let observerCallback: IntersectionObserverCallback;

beforeEach(() => {
  news = async () => json(page());
  fetchMock = vi.fn(async (input: string) => {
    const url = String(input);
    if (url.includes("/meta")) return json({version: "0.2.0", regions: ["world", "japan"], languages: ["en", "ja"], categories: ["world"], source_count: 1, article_count: 1, last_sync_at: null});
    if (url.includes("/sources")) return json([source]);
    return news(url);
  });
  vi.stubGlobal("fetch", fetchMock);
  vi.stubGlobal("IntersectionObserver", class {
    constructor(callback: IntersectionObserverCallback) { observerCallback = callback; }
    observe() {} disconnect() {} unobserve() {}
  });
});
afterEach(() => { wrapper?.unmount(); wrapper = undefined; vi.unstubAllGlobals(); vi.restoreAllMocks(); });
async function render() { wrapper = mount(HomeView); await flushPromises(); return wrapper; }

describe("News timeline", () => {
  it("loads real API shape and shows a publisher and original link", async () => {
    const view = await render();
    expect(view.findAll("article")).toHaveLength(1);
    expect(view.text()).toContain("Example Publisher");
    expect(view.find(".original-link").attributes("rel")).toBe("noopener noreferrer");
    expect(fetchMock.mock.calls.some(([url]) => String(url).startsWith("/api/v1/news?"))).toBe(true);
  });
  it("shows skeletons while the first page is in flight", async () => {
    news = () => new Promise(() => {});
    wrapper = mount(HomeView);
    await wrapper.vm.$nextTick();
    expect(wrapper.find('[aria-label="Loading news"]').exists()).toBe(true);
    expect(wrapper.findAll(".skeleton-card")).toHaveLength(5);
  });
  it("shows an empty state", async () => {
    news = async () => json(page([]));
    expect((await render()).text()).toContain("No stories found");
  });
  it("shows a retry and recovers after an HTTP failure", async () => {
    news = async () => new Response("", {status: 503});
    const view = await render();
    expect(view.find('[role="alert"]').exists()).toBe(true);
    news = async () => json(page());
    await view.find('[role="alert"] button').trigger("click");
    await flushPromises();
    expect(view.findAll("article")).toHaveLength(1);
  });
  it("rejects HTML returned by a misconfigured API proxy", async () => {
    news = async () => new Response("<html>not an API</html>", {headers: {"content-type": "text/html"}});
    expect((await render()).find('[role="alert"]').exists()).toBe(true);
  });
  it("resets articles and requests the selected region", async () => {
    news = async url => json(page([article(url.includes("region=japan") ? 2 : 1)]));
    const view = await render();
    await view.findAll(".topic-tabs button").find(b => b.text() === "Japan")!.trigger("click");
    await flushPromises();
    expect(view.findAll("article")).toHaveLength(1);
    expect(view.find("article").attributes("data-news-id")).toBe("2");
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes("region=japan"))).toBe(true);
  });
  it("searches only when submitted", async () => {
    const view = await render();
    await view.find('input[type="search"]').setValue("climate");
    await view.find("form").trigger("submit");
    await flushPromises();
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes("q=climate"))).toBe(true);
  });
  it("appends cursor pages without duplicate IDs", async () => {
    news = async url => json(url.includes("cursor=") ? page([article(1), article(2)]) : page([article(1)], "opaque"));
    const view = await render();
    await view.find(".load-more button").trigger("click");
    await flushPromises();
    expect(view.findAll("article")).toHaveLength(2);
    expect(view.text()).toContain("You're all caught up.");
  });
  it("loads another page when the sentinel is visible", async () => {
    news = async url => json(url.includes("cursor=") ? page([article(2)]) : page([article(1)], "next"));
    const view = await render();
    observerCallback([{isIntersecting: true} as IntersectionObserverEntry], {} as IntersectionObserver);
    await flushPromises();
    expect(view.findAll("article")).toHaveLength(2);
  });
  it("keeps existing articles visible during refresh", async () => {
    const view = await render();
    let resolve: (response: Response) => void = () => {};
    news = () => new Promise(r => { resolve = r; });
    await view.find(".refresh-button").trigger("click");
    expect(view.findAll("article")).toHaveLength(1);
    expect(view.find(".skeleton-list").exists()).toBe(false);
    resolve(json(page([article(2)])));
    await flushPromises();
    expect(view.find("article").attributes("data-news-id")).toBe("2");
  });
  it("ignores an old response after filters change", async () => {
    let resolveOld: (response: Response) => void = () => {};
    news = url => url.includes("region=japan") ? Promise.resolve(json(page([article(2)]))) : new Promise(r => { resolveOld = r; });
    wrapper = mount(HomeView);
    await wrapper.findAll(".topic-tabs button").find(b => b.text() === "Japan")!.trigger("click");
    await flushPromises();
    resolveOld(json(page([article(1)])));
    await flushPromises();
    expect(wrapper.find("article").attributes("data-news-id")).toBe("2");
  });
  it("labels cached responses as potentially stale", async () => {
    news = async () => json(page(), {"X-News-Cache": "hit"});
    expect((await render()).find(".status-notice").text()).toContain("Showing cached news");
  });
  it("guards repeated load-more requests", async () => {
    let count = 0;
    news = async url => {
      if (url.includes("cursor=")) { count++; return new Promise(() => {}); }
      return json(page([article()], "next"));
    };
    await render();
    observerCallback([{isIntersecting: true} as IntersectionObserverEntry], {} as IntersectionObserver);
    observerCallback([{isIntersecting: true} as IntersectionObserverEntry], {} as IntersectionObserver);
    expect(count).toBe(1);
  });
});

describe("News card and relative time", () => {
  it("supports no image and Unicode long headlines", () => {
    wrapper = mount(NewsCard, {props: {article: article(1, {title: "中文 日本語 News ".repeat(30), summary: null})}});
    expect(wrapper.find("img").exists()).toBe(false);
    expect(wrapper.find("h2").text()).toContain("日本語");
    expect(wrapper.find("time").attributes("datetime")).toBeTruthy();
  });
  it("removes failed images while keeping the article", async () => {
    wrapper = mount(NewsCard, {props: {article: article(1, {image_url: "https://example.org/photo.jpg"})}});
    expect(wrapper.find("img").attributes("loading")).toBe("lazy");
    await wrapper.find("img").trigger("error");
    expect(wrapper.find("img").exists()).toBe(false);
    expect(wrapper.find("h2").exists()).toBe(true);
  });
  it.each([[0, "Just now"], [3, "3m"], [18, "18m"], [120, "2h"]])("formats %s minutes", (minutes, expected) => {
    const now = Date.now();
    expect(formatRelativeTime(new Date(now - Number(minutes) * 60000).toISOString(), now)).toBe(expected);
  });
  it("does not turn invalid dates into current news", () => {
    expect(formatRelativeTime("not-a-date")).toBe("Unknown time");
  });
});
