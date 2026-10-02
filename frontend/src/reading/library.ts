import {reactive} from "vue";
import type {NewsArticle} from "../types/news";

export const MAX_BOOKMARKS = 500;
export const MAX_READ = 5000;
export const MAX_IMPORT_BYTES = 2 * 1024 * 1024;
export const LIBRARY_KEY = `global-news:reading:v1:${import.meta.env.BASE_URL}`;
export type FontSize = "normal" | "large" | "larger";
export interface Bookmark {
  url: string;
  title: string;
  summary: string | null;
  published_at: string;
  source_name: string;
  language: string;
  saved_at: string;
}
interface StoredLibrary {
  schema_version: 1;
  bookmarks: Bookmark[];
  read: string[];
  font: FontSize;
}
type StorageLike = Pick<Storage, "getItem" | "setItem">;

export function safeArticleUrl(value: unknown): value is string {
  if (typeof value !== "string" || value.length > 4096) return false;
  try {
    const url = new URL(value);
    return ["http:", "https:"].includes(url.protocol) && !url.username && !url.password;
  } catch { return false; }
}

function text(value: unknown, max: number): value is string {
  return typeof value === "string" && value.trim().length > 0 && value.length <= max;
}

export function parseBookmark(value: unknown): Bookmark {
  if (!value || typeof value !== "object") throw new Error("收藏格式不正确。");
  const b = value as Record<string, unknown>;
  if (!safeArticleUrl(b.url) || !text(b.title, 1000) || !text(b.source_name, 300)
      || !text(b.language, 40) || !text(b.published_at, 80) || !Number.isFinite(Date.parse(b.published_at))
      || !text(b.saved_at, 80) || !Number.isFinite(Date.parse(b.saved_at))
      || !(b.summary === null || (typeof b.summary === "string" && b.summary.length <= 4000))) {
    throw new Error("收藏中包含无效链接、日期或超长内容，未导入任何数据。");
  }
  return {url: b.url, title: b.title, summary: b.summary, published_at: b.published_at,
    source_name: b.source_name, language: b.language, saved_at: b.saved_at};
}

export function parseImport(raw: string): Bookmark[] {
  if (new Blob([raw]).size > MAX_IMPORT_BYTES) throw new Error("文件超过 2 MB，未导入。");
  let data: unknown;
  try { data = JSON.parse(raw); } catch { throw new Error("这不是有效的 JSON 收藏文件。"); }
  if (!data || typeof data !== "object") throw new Error("不支持的收藏文件格式。");
  const envelope = data as Record<string, unknown>;
  if (envelope.schema_version !== 1 || !Array.isArray(envelope.bookmarks)
      || envelope.bookmarks.length > MAX_BOOKMARKS) {
    throw new Error("仅支持版本 1 的收藏文件，每次最多 500 条。");
  }
  return envelope.bookmarks.map(parseBookmark);
}

export function createReadingLibrary(storage: StorageLike | null, key = LIBRARY_KEY) {
  const state = reactive<StoredLibrary & {warning: string}>({
    schema_version: 1, bookmarks: [], read: [], font: "normal", warning: ""
  });
  try {
    const raw = storage?.getItem(key);
    if (raw) {
      const data = JSON.parse(raw);
      const bookmarks = parseImport(raw);
      if (!Array.isArray(data.read) || data.read.length > MAX_READ || !data.read.every(safeArticleUrl)
          || !["normal", "large", "larger"].includes(data.font)) throw new Error("invalid library");
      state.bookmarks = [...new Map(bookmarks.map(b => [b.url, b])).values()];
      state.read = [...new Set<string>(data.read)];
      state.font = data.font;
    }
    if (!storage) state.warning = "浏览器存储不可用，本次操作仅在当前页面有效。请导出收藏备份。";
  } catch {
    state.warning = "本地阅读数据无法读取，原始记录未被删除。导出或恢复前请勿清理浏览器数据。";
  }

  function persist() {
    if (!storage) return;
    try {
      const data: StoredLibrary = {schema_version: 1, bookmarks: state.bookmarks, read: state.read, font: state.font};
      storage.setItem(key, JSON.stringify(data));
      state.warning = "";
    } catch {
      state.warning = "浏览器未能保存本次修改，刷新后可能丢失。请导出收藏备份。";
    }
  }
  function toggleBookmark(article: NewsArticle) {
    const index = state.bookmarks.findIndex(b => b.url === article.url);
    if (index >= 0) state.bookmarks.splice(index, 1);
    else {
      if (state.bookmarks.length >= MAX_BOOKMARKS) throw new Error("最多保存 500 条收藏，请先导出并移除部分收藏。");
      state.bookmarks.unshift(parseBookmark({url: article.url, title: article.title, summary: article.summary,
        published_at: article.published_at, source_name: article.source.name, language: article.language,
        saved_at: new Date().toISOString()}));
    }
    persist();
  }
  function removeBookmark(url: string) {
    state.bookmarks = state.bookmarks.filter(b => b.url !== url);
    persist();
  }
  function toggleRead(url: string) {
    if (!safeArticleUrl(url)) return;
    state.read = state.read.includes(url) ? state.read.filter(item => item !== url)
      : [url, ...state.read].slice(0, MAX_READ);
    persist();
  }
  function setFont(font: FontSize) {
    if (!["normal", "large", "larger"].includes(font)) return;
    state.font = font;
    persist();
  }
  function importBookmarks(raw: string) {
    const incoming = parseImport(raw);
    const merged = new Map(state.bookmarks.map(b => [b.url, b]));
    for (const b of incoming) if (!merged.has(b.url)) merged.set(b.url, b);
    if (merged.size > MAX_BOOKMARKS) throw new Error("合并后超过 500 条，未导入任何数据。请先整理现有收藏。");
    const added = merged.size - state.bookmarks.length;
    state.bookmarks = [...merged.values()];
    persist();
    return added;
  }
  function exportBookmarks() {
    return JSON.stringify({schema_version: 1, exported_at: new Date().toISOString(), bookmarks: state.bookmarks}, null, 2);
  }
  function reload() {
    const other = createReadingLibrary(storage, key);
    if (other.state.warning) { state.warning = other.state.warning; return; }
    state.bookmarks = other.state.bookmarks;
    state.read = other.state.read;
    state.font = other.state.font;
    state.warning = "";
  }
  return {state, toggleBookmark, removeBookmark, toggleRead, setFont, importBookmarks, exportBookmarks, reload};
}

function browserStorage() {
  try { return typeof window !== "undefined" ? window.localStorage : null; } catch { return null; }
}
export const readingLibrary = createReadingLibrary(browserStorage());
if (typeof window !== "undefined") window.addEventListener("storage", event => {
  if (event.key === LIBRARY_KEY || event.key === null) readingLibrary.reload();
});
