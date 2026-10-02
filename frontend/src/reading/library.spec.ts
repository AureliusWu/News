import {describe, expect, it} from "vitest";
import type {NewsArticle} from "../types/news";
import {createReadingLibrary, parseImport, safeArticleUrl} from "./library";
import {filtersFromQuery, queryFromFilters} from "./filterLocation";
import {healthDescription, parseHealthReport} from "./sourceHealth";

const article = {url: "https://example.org/news/one", title: "A real headline", summary: null,
  source: {name: "Example"}, language: "en", published_at: "2026-09-29T00:00:00Z"} as NewsArticle;
function storage() {
  const data = new Map<string, string>();
  return {getItem: (key: string) => data.get(key) ?? null, setItem: (key: string, value: string) => { data.set(key, value); }};
}
describe("reading library", () => {
  it("reloads a second tab's update without overwriting the shared storage", () => {
    const disk = storage(); const first = createReadingLibrary(disk); const second = createReadingLibrary(disk);
    second.toggleBookmark(article); second.setFont("large"); first.reload();
    expect(first.state.bookmarks).toHaveLength(1); expect(first.state.font).toBe("large");
    disk.setItem("broken", "{bad");
    const corrupted = createReadingLibrary(disk, "broken"); corrupted.reload();
    expect(disk.getItem("broken")).toBe("{bad");
  });
  it("persists a bookmark and removes it on a second toggle", () => {
    const disk = storage(); const a = createReadingLibrary(disk);
    a.toggleBookmark(article);
    expect(createReadingLibrary(disk).state.bookmarks[0].title).toBe(article.title);
    a.toggleBookmark(article); expect(a.state.bookmarks).toHaveLength(0);
  });
  it("round trips export/import without overwriting a duplicate", () => {
    const a = createReadingLibrary(storage()); a.toggleBookmark(article);
    const b = createReadingLibrary(storage());
    expect(b.importBookmarks(a.exportBookmarks())).toBe(1);
    expect(b.importBookmarks(a.exportBookmarks())).toBe(0);
    expect(b.state.bookmarks[0].published_at).toBe(article.published_at);
  });
  it("never imports read status, font or unrelated fields", () => {
    const a = createReadingLibrary(storage()); a.toggleBookmark(article);
    const payload = JSON.parse(a.exportBookmarks()); payload.read = [article.url]; payload.font = "larger";
    const b = createReadingLibrary(storage()); b.importBookmarks(JSON.stringify(payload));
    expect(b.state.read).toEqual([]); expect(b.state.font).toBe("normal");
  });
  it.each(["javascript:alert(1)", "data:text/html,hi", "file:///secret", "https://user:secret@example.org", "bad"])("rejects unsafe link %s", url => {
    expect(safeArticleUrl(url)).toBe(false);
  });
  it("validates the entire import before mutation", () => {
    const a = createReadingLibrary(storage()); a.toggleBookmark(article);
    const payload = JSON.parse(a.exportBookmarks()); payload.bookmarks.push({...payload.bookmarks[0], url: "javascript:alert(1)"});
    expect(() => a.importBookmarks(JSON.stringify(payload))).toThrow();
    expect(a.state.bookmarks).toHaveLength(1);
  });
  it("rejects invalid timestamps and unsupported versions", () => {
    expect(() => parseImport('{"schema_version":2,"bookmarks":[]}')).toThrow();
    const a = createReadingLibrary(storage()); a.toggleBookmark(article);
    const data = JSON.parse(a.exportBookmarks()); data.bookmarks[0].published_at = "unknown";
    expect(() => parseImport(JSON.stringify(data))).toThrow();
  });
  it("rejects oversized input and too many records", () => {
    expect(() => parseImport("x".repeat(2 * 1024 * 1024 + 1))).toThrow();
    expect(() => parseImport(JSON.stringify({schema_version: 1, bookmarks: Array(501).fill({})}))).toThrow();
  });
  it("handles unavailable or full storage without blocking reading", () => {
    const a = createReadingLibrary(null); a.toggleBookmark(article);
    expect(a.state.bookmarks).toHaveLength(1); expect(a.state.warning).not.toBe("");
    const b = createReadingLibrary({getItem: () => null, setItem: () => { throw new Error("QuotaExceeded"); }});
    b.toggleBookmark(article); expect(b.state.bookmarks).toHaveLength(1); expect(b.state.warning).toContain("未能保存");
  });
  it("does not overwrite damaged storage on initialization", () => {
    const disk = storage(); disk.setItem("broken", "{bad");
    const a = createReadingLibrary(disk, "broken");
    expect(a.state.warning).not.toBe(""); expect(disk.getItem("broken")).toBe("{bad");
  });
  it("persists font and explicit read/unread state", () => {
    const disk = storage(); const a = createReadingLibrary(disk);
    a.toggleRead(article.url); a.setFont("larger");
    const b = createReadingLibrary(disk); expect(b.state.read).toEqual([article.url]); expect(b.state.font).toBe("larger");
    b.toggleRead(article.url); expect(b.state.read).toEqual([]);
  });
  it("bounds and deduplicates read history", () => {
    const disk = storage(); disk.setItem("test", JSON.stringify({schema_version: 1, bookmarks: [], font: "normal", read: Array.from({length: 5000}, (_, i) => `https://example.org/${i}`)}));
    const a = createReadingLibrary(disk, "test"); a.toggleRead(article.url);
    expect(a.state.read).toHaveLength(5000); expect(a.state.read[0]).toBe(article.url);
  });
});
describe("shareable filters", () => {
  it("round trips Chinese and raw API codes", () => {
    const filters = {q: "中文 标题", region: "japan", category: "", language: "ja", source: "nhk-japan"};
    const params = Object.fromEntries(new URLSearchParams(queryFromFilters(filters)));
    expect(filtersFromQuery(params)).toEqual(filters);
  });
  it("discards arrays, unknown keys and overlong values", () => {
    const filters = filtersFromQuery({q: "x".repeat(500), source: ["a", "b"], token: "secret"});
    expect(filters.q.length).toBe(200); expect(filters.source).toBe("");
    expect(queryFromFilters(filters)).not.toHaveProperty("token");
  });
});
describe("source health semantics", () => {
  const source = {id: "one", name: "One", publisher: "Publisher", health: "FAIL" as const, entry_count: 0, latest_entry: null, notes: "No valid articles with original publication dates within seven days"};
  it("does not confuse no recent entries with unreachable upstream", () => { expect(healthDescription(source)).toContain("不能据此判定"); });
  it.each([["ReadTimeout", "采集超时"], ["Upstream HTTP 403", "上游限制访问"], ["Upstream HTTP 404", "订阅地址不存在"]])("classifies %s", (notes, label) => { expect(healthDescription({...source, notes})).toBe(label); });
  it("preserves unknown publication date", () => { expect(parseHealthReport({checked_at: new Date().toISOString(), sources: [source]}).sources[0].latest_entry).toBeNull(); });
  it("rejects duplicate sources and future report dates", () => {
    expect(() => parseHealthReport({checked_at: new Date().toISOString(), sources: [source, source]})).toThrow();
    expect(() => parseHealthReport({checked_at: "2099-01-01T00:00:00Z", sources: [source]})).toThrow();
  });
});
