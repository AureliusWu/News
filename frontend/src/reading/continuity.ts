import {reactive} from 'vue';
import type {EventIndex, NewsEvent} from '../types/events';
import type {NewsFilters} from '../types/news';
import {FILTER_KEYS, filtersFromQuery} from './filterLocation';

export const CONTINUITY_KEY = `global-news:continuity:v1:${import.meta.env.BASE_URL}`;
export const MAX_FOLLOWS = 100;
export const MAX_VIEWS = 20;
export const MAX_SEEN_IDS = 10000;
export const MAX_CONTINUITY_BYTES = 2 * 1024 * 1024;
export interface Follow {event_id: string; title: string; seen_article_ids: string[]; followed_at: string}
export interface SavedView {id: string; name: string; filters: NewsFilters}
interface Stored {schema_version: 1; kind: 'news-continuity'; follows: Follow[]; views: SavedView[]}
type Disk = Pick<Storage, 'getItem' | 'setItem'>;
const eventId = (value: unknown): value is string => typeof value === 'string' && /^e_[a-f0-9]{24}$/.test(value);
const identity = (value: unknown): value is string => typeof value === 'string' && /^[a-zA-Z0-9_-]{1,100}$/.test(value);
const text = (value: unknown, limit: number): value is string => typeof value === 'string' && !!value.trim() && value.length <= limit;

export function parseContinuity(raw: string): Stored {
  if (new Blob([raw]).size > MAX_CONTINUITY_BYTES) throw new Error('关注备份超过 2 MB，未导入。');
  const data = JSON.parse(raw) as Stored;
  if (data?.schema_version !== 1 || data.kind !== 'news-continuity' || !Array.isArray(data.follows)
      || !Array.isArray(data.views) || data.follows.length > MAX_FOLLOWS || data.views.length > MAX_VIEWS)
    throw new Error('关注与筛选备份格式不正确，最多 100 个事件、20 个方案。');
  const follows = data.follows.map(item => {
    if (!item || !eventId(item.event_id) || !text(item.title, 1000) || !text(item.followed_at, 80)
        || !Number.isFinite(Date.parse(item.followed_at)) || !Array.isArray(item.seen_article_ids)
        || !item.seen_article_ids.every(identity)) throw new Error('关注事件包含无效记录，未导入。');
    return {event_id: item.event_id, title: item.title, followed_at: item.followed_at,
      seen_article_ids: [...new Set(item.seen_article_ids)]};
  });
  const views = data.views.map(item => {
    if (!item || !identity(item.id) || !text(item.name, 40) || !item.filters
        || FILTER_KEYS.some(key => typeof item.filters[key] !== 'string' || item.filters[key].length > (key === 'q' ? 200 : 100)))
      throw new Error('筛选方案包含无效内容，未导入。');
    return {id: item.id, name: item.name.trim(), filters: filtersFromQuery({...item.filters})};
  });
  if (new Set(follows.map(item => item.event_id)).size !== follows.length
      || new Set(views.map(item => item.id)).size !== views.length
      || follows.reduce((sum, item) => sum + item.seen_article_ids.length, 0) > MAX_SEEN_IDS)
    throw new Error('备份有重复标识或超过 10000 条已见报道记录，未导入。');
  return {schema_version: 1, kind: 'news-continuity', follows, views};
}

export function createContinuity(storage: Disk | null, key = CONTINUITY_KEY) {
  const state = reactive<Stored & {warning: string}>({schema_version: 1, kind: 'news-continuity', follows: [], views: [], warning: ''});
  let original: string | null = null;
  let protectedRecord = false;
  const record = (): Stored => ({schema_version: 1, kind: 'news-continuity', follows: state.follows, views: state.views});
  function reload() {
    try {
      original = storage?.getItem(key) ?? null;
      const parsed = original ? parseContinuity(original) : {follows: [], views: []};
      state.follows = parsed.follows; state.views = parsed.views; protectedRecord = false;
      state.warning = storage ? '' : '浏览器存储不可用，关注与筛选仅在当前页面有效，请导出备份。';
    } catch {
      protectedRecord = true;
      state.warning = '关注与筛选记录损坏或无法读取，已阻止覆盖原记录。请先备份原始浏览器数据。';
    }
  }
  reload();
  function change(edit: (next: Stored) => void) {
    const next = parseContinuity(JSON.stringify(record()));
    edit(next);
    const checked = parseContinuity(JSON.stringify(next));
    state.follows = checked.follows; state.views = checked.views;
    if (!storage || protectedRecord) return;
    try {
      if (storage.getItem(key) !== original) throw new Error('concurrent update');
      const raw = JSON.stringify(checked);
      storage.setItem(key, raw); original = raw; state.warning = '';
    } catch {
      state.warning = '关注与筛选未能保存，或其他页面已修改记录。本次修改仅在内存中，请先导出备份再刷新。';
    }
  }
  const isFollowing = (id: string) => state.follows.some(item => item.event_id === id);
  function toggleFollow(event: NewsEvent) {
    change(next => {
      if (next.follows.some(item => item.event_id === event.event_id)) next.follows = next.follows.filter(item => item.event_id !== event.event_id);
      else next.follows.unshift({event_id: event.event_id, title: event.title,
        followed_at: new Date().toISOString(), seen_article_ids: [...event.article_ids]});
    });
  }
  function removeFollow(id: string) { change(next => { next.follows = next.follows.filter(item => item.event_id !== id); }); }
  function synchronize(index: EventIndex) {
    if (!state.follows.length) return;
    const next = parseContinuity(JSON.stringify(record()));
    const merged = new Map<string, Follow>();
    for (const follow of next.follows) {
      const id = Object.prototype.hasOwnProperty.call(index.aliases || {}, follow.event_id) ? index.aliases![follow.event_id] : follow.event_id;
      const event = index.events.find(item => item.event_id === id);
      const previous = merged.get(id);
      merged.set(id, {...follow, event_id: id, title: event?.title ?? follow.title,
        followed_at: previous?.followed_at ?? follow.followed_at,
        seen_article_ids: [...new Set([...(previous?.seen_article_ids || []), ...follow.seen_article_ids])]});
    }
    const follows = [...merged.values()];
    if (JSON.stringify(follows) !== JSON.stringify(state.follows)) change(value => { value.follows = follows; });
  }
  function newCount(event: NewsEvent): number {
    const follow = state.follows.find(item => item.event_id === event.event_id);
    if (!follow) return 0;
    const seen = new Set(follow.seen_article_ids);
    return new Set(event.article_ids.filter(id => !seen.has(id))).size;
  }
  function markSeen(event: NewsEvent) {
    change(next => {
      const follow = next.follows.find(item => item.event_id === event.event_id);
      if (follow) follow.seen_article_ids = [...new Set([...follow.seen_article_ids, ...event.article_ids])];
    });
  }
  function saveView(name: string, filters: NewsFilters, id?: string) {
    change(next => {
      const existing = id ? next.views.find(item => item.id === id) : undefined;
      if (id && !existing) throw new Error('原筛选方案已不存在，请另存为新方案。');
      const value = {id: existing?.id ?? `v_${crypto.randomUUID()}`, name: name.trim(), filters: filtersFromQuery({...filters})};
      if (existing) Object.assign(existing, value); else next.views.push(value);
    });
  }
  function removeView(id: string) { change(next => { next.views = next.views.filter(item => item.id !== id); }); }
  function importBackup(raw: string) {
    const incoming = parseContinuity(raw);
    change(next => {
      for (const item of incoming.follows) {
        const existing = next.follows.find(value => value.event_id === item.event_id);
        if (existing) existing.seen_article_ids = [...new Set([...existing.seen_article_ids, ...item.seen_article_ids])];
        else next.follows.push(item);
      }
      for (const item of incoming.views) if (!next.views.some(value => value.id === item.id)) next.views.push(item);
    });
  }
  return {state, isFollowing, toggleFollow, removeFollow, synchronize, newCount, markSeen, saveView, removeView,
    importBackup, exportBackup: () => JSON.stringify(record(), null, 2), reload};
}
function browserStorage() { try { return typeof window === 'undefined' ? null : window.localStorage; } catch { return null; } }
export const continuity = createContinuity(browserStorage());
if (typeof window !== 'undefined') window.addEventListener('storage', event => {
  if (event.key === CONTINUITY_KEY || event.key === null) continuity.reload();
});
