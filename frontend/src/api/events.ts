import {getProvider} from "./providers";
import type {Snapshot} from "../snapshot/transport";
import type {EventIndex} from "../types/events";

export function validateEventIndex(value: unknown, snapshot: Snapshot): EventIndex {
  const index = value as EventIndex;
  if (!index || index.schema_version !== 1 || index.snapshot_id !== snapshot.snapshot_id
      || index.content_sha256 !== snapshot.content_sha256 || index.generated_at !== snapshot.generated_at
      || index.method_version !== "lexical-complete-link-v1" || !Array.isArray(index.events) || index.events.length > 5000) throw new Error("事件报告版本不兼容，请刷新后重试。");
  const ids = new Set<string>();
  const articles = new Map(snapshot.articles.map(a => [(a as typeof a & {article_id?: string}).article_id, a]));
  const used = new Set<string>();
  for (const event of index.events) {
    if (!/^e_[a-f0-9]{24}$/.test(event.event_id) || ids.has(event.event_id)
        || typeof event.title !== "string" || !event.title.trim() || event.title.length > 1000
        || typeof event.language !== "string" || !Number.isFinite(Date.parse(event.first_published_at))
        || !Number.isFinite(Date.parse(event.last_published_at)) || Date.parse(event.first_published_at) > Date.parse(event.last_published_at)
        || !Array.isArray(event.article_ids) || !event.article_ids.length || event.article_count !== event.article_ids.length
        || !Array.isArray(event.publisher_ids) || new Set(event.publisher_ids).size !== event.publisher_ids.length
        || event.publisher_count !== event.publisher_ids.length || !event.publisher_count
        || !Array.isArray(event.source_names) || !event.source_names.every(name => typeof name === "string")) throw new Error("事件报告包含无效记录。");
    ids.add(event.event_id);
    for (const articleId of event.article_ids) {
      const article = articles.get(articleId) as (typeof snapshot.articles[number] & {event_id?: string}) | undefined;
      if (!article || article.event_id !== event.event_id || used.has(articleId)) throw new Error("事件引用了其他版本或重复的文章。");
      used.add(articleId);
    }
    const actualPublishers = new Set(event.article_ids.map(id => (articles.get(id)!.source as typeof snapshot.sources[number] & {publisher_id?: string}).publisher_id));
    if (actualPublishers.size !== event.publisher_count || event.publisher_ids.some(id => !actualPublishers.has(id))) throw new Error("事件发布机构计数与文章证据不一致。");
  }
  if (used.size !== snapshot.articles.length) throw new Error("事件报告未覆盖当前新闻快照。");
  if (index.aliases !== undefined) {
    if (!index.aliases || typeof index.aliases !== "object" || Array.isArray(index.aliases) || Object.keys(index.aliases).length > 5000) throw new Error("事件历史链接格式无效。");
    for (const [old, target] of Object.entries(index.aliases)) {
      if (!/^e_[a-f0-9]{24}$/.test(old) || ids.has(old) || typeof target !== "string" || !ids.has(target) || old === target) throw new Error("事件历史链接必须直接指向当前事件。");
    }
  }
  return index;
}
export function resolveEventId(index: EventIndex, requested: string): string {
  return Object.prototype.hasOwnProperty.call(index.aliases || {}, requested) ? index.aliases![requested] : requested;
}
export async function getEvents(signal?: AbortSignal) {
  const provider = getProvider();
  const snapshot = await provider.snapshot(signal);
  if (!snapshot.events_file) throw new Error("当前快照尚未包含事件聚合，请等待新版数据发布。");
  const index = validateEventIndex(await provider.asset(snapshot, snapshot.events_file, signal), snapshot);
  return {snapshot, index};
}
