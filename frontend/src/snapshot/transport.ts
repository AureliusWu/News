import './snapshot.css';
import {ui} from '../locales/zh-CN';
import {formatDateTime} from '../utils/time';

type Source = {
  id: number; slug: string; name: string; publisher: string; homepage: string;
  country: string; region: string; language: string; category: string;
  source_type: string; health_status: string; enabled: boolean;
};
type Article = {
  id: number; title: string; summary: string; url: string; image_url: string | null;
  source: Source; region: string; language: string; category: string; published_at: string;
};
export type Snapshot = {
  schema_version: number; generated_at: string; content_sha256: string;
  articles: Article[]; sources: Source[];
  meta: {
    version: string; regions: string[]; categories: string[]; languages: string[];
    source_count: number; article_count: number; last_sync_at: string;
    publication_mode: string;
  };
  health: { configured: number; healthy: number; failed: number; gate_pass: boolean };
};
type Loaded = { snapshot: Snapshot; cached: boolean; checkedAt: number };
type Options = {
  origin: string; basePath: string; now?: () => number; storage?: CacheStorage;
  onState?: (state: Loaded | { error: string }) => void;
};
const MAX_AGE = 72 * 60 * 60 * 1000;
const validUrl = (value: unknown) => {
  if (typeof value !== 'string') return false;
  try {
    const u = new URL(value);
    return ['http:', 'https:'].includes(u.protocol) && !u.username && !u.password;
  } catch { return false; }
};

export function validateSnapshot(value: unknown, now = Date.now()): Snapshot {
  const s = value as Snapshot;
  const generated = Date.parse(s?.generated_at);
  if (!s || s.schema_version !== 1 || !Number.isFinite(generated) ||
      generated > now + 300000 || now - generated > MAX_AGE ||
      !/^[a-f0-9]{64}$/.test(s.content_sha256 || '') ||
      !Array.isArray(s.articles) || !s.articles.length || s.articles.length > 5000 ||
      !Array.isArray(s.sources) || !s.health?.gate_pass ||
      s.meta?.article_count !== s.articles.length || s.meta.publication_mode !== 'snapshot') {
    throw new Error('News snapshot is invalid or more than 72 hours old.');
  }
  const slugs = new Set(s.sources.map(source => source.slug));
  const ids = new Set<number>();
  const urls = new Set<string>();
  for (const article of s.articles) {
    const published = Date.parse(article.published_at);
    if (!Number.isSafeInteger(article.id) || ids.has(article.id) || urls.has(article.url) ||
        typeof article.title !== 'string' || !article.title.trim() ||
        typeof article.summary !== 'string' || !validUrl(article.url) ||
        (article.image_url !== null && !validUrl(article.image_url)) ||
        !slugs.has(article.source?.slug) || !Number.isFinite(published) ||
        published > now + 3600000) throw new Error('News snapshot contains invalid articles.');
    ids.add(article.id); urls.add(article.url);
  }
  return s;
}
const json = (body: unknown, status = 200, cached = false) => new Response(JSON.stringify(body), {
  status, headers: {
    'Content-Type': 'application/json', 'X-News-Mode': 'snapshot',
    ...(cached ? { 'X-Cache-Stale': 'true' } : {}),
  },
});
const encodeCursor = (value: unknown) => btoa(String.fromCharCode(...new TextEncoder().encode(JSON.stringify(value))))
  .replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
const decodeCursor = (value: string) => {
  const raw = value.replace(/-/g, '+').replace(/_/g, '/');
  return JSON.parse(new TextDecoder().decode(Uint8Array.from(atob(raw.padEnd(Math.ceil(raw.length / 4) * 4, '=')), c => c.charCodeAt(0))));
};

export function querySnapshot(snapshot: Snapshot, endpoint: string, params: URLSearchParams, cached = false): Response {
  if (endpoint === 'meta') return json(snapshot.meta, 200, cached);
  if (endpoint === 'sources') return json(snapshot.sources, 200, cached);
  if (endpoint === 'health') return json({
    status: 'snapshot', mode: 'snapshot', version: snapshot.meta.version,
    generated_at: snapshot.generated_at, cached, database: 'not_applicable', ...snapshot.health,
  }, 200, cached);
  if (endpoint !== 'news') return json({ detail: 'No live backend exists in snapshot mode.' }, 404);
  const limit = Number(params.get('limit') || '20');
  const q = (params.get('q') || '').trim().toLocaleLowerCase();
  if (!Number.isInteger(limit) || limit < 1 || limit > 100 || q.length > 200) return json({ detail: 'Invalid page size or search text.' }, 422);
  const filters = ['region', 'category', 'language', 'source'].map(key => params.get(key) || '');
  const signature = JSON.stringify([...filters, q]);
  const items = snapshot.articles.filter(article =>
    (!filters[0] || article.region === filters[0]) &&
    (!filters[1] || article.category === filters[1]) &&
    (!filters[2] || article.language === filters[2]) &&
    (!filters[3] || article.source.slug === filters[3] || String(article.source.id) === filters[3]) &&
    (!q || `${article.title} ${article.summary}`.toLocaleLowerCase().includes(q)));
  let offset = 0;
  if (params.has('cursor')) {
    try {
      if ((params.get('cursor') || '').length > 4096) throw new Error('oversize');
      const cursor = decodeCursor(params.get('cursor') || '');
      if (cursor.g !== snapshot.content_sha256) return json({ detail: 'Snapshot changed. Refresh the news list.' }, 409);
      if (cursor.v !== 1 || cursor.f !== signature || !Number.isInteger(cursor.o) || cursor.o < 0 || cursor.o > items.length) throw new Error('invalid');
      offset = cursor.o;
    } catch { return json({ detail: 'Invalid snapshot cursor.' }, 400); }
  }
  const end = offset + limit;
  return json({
    items: items.slice(offset, end), has_more: end < items.length,
    next_cursor: end < items.length ? encodeCursor({ v: 1, g: snapshot.content_sha256, f: signature, o: end }) : null,
  }, 200, cached);
}

function abortable<T>(promise: Promise<T>, signal?: AbortSignal | null): Promise<T> {
  if (!signal) return promise;
  if (signal.aborted) return Promise.reject(new DOMException('Aborted', 'AbortError'));
  return new Promise((resolve, reject) => {
    const abort = () => reject(new DOMException('Aborted', 'AbortError'));
    signal.addEventListener('abort', abort, { once: true });
    promise.then(resolve, reject).finally(() => signal.removeEventListener('abort', abort));
  });
}

export function createSnapshotFetch(nativeFetch: typeof fetch, options: Options): typeof fetch {
  const now = options.now || Date.now;
  const base = `/${options.basePath.replace(/^\/+|\/+$/g, '')}${options.basePath.replace(/\//g, '') ? '/' : ''}`;
  const dataUrl = new URL(`${base}data/news.json`, options.origin).href;
  let memory: Loaded | undefined;
  let pending: Promise<Loaded> | undefined;
  const load = (): Promise<Loaded> => {
    if (memory && now() - memory.checkedAt < 60000) return Promise.resolve(memory);
    if (pending) return pending;
    pending = (async () => {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 12000);
      let cache: Cache | undefined;
      try { cache = await options.storage?.open(`global-news-snapshot-v1:${base}`); } catch { /* Storage may be disabled. */ }
      try {
        const response = await nativeFetch(dataUrl, { cache: 'no-store', credentials: 'omit', signal: controller.signal });
        if (!response.ok) throw new Error(`Snapshot download failed (${response.status}).`);
        const snapshot = validateSnapshot(await response.json(), now());
        memory = { snapshot, cached: false, checkedAt: now() };
        try { await cache?.put(dataUrl, json(snapshot)); } catch { /* Cache quota must not break online news. */ }
      } catch (error) {
        let fallback: Snapshot | undefined;
        try {
          if (memory) fallback = validateSnapshot(memory.snapshot, now());
          else {
            const saved = await cache?.match(dataUrl);
            if (saved) fallback = validateSnapshot(await saved.json(), now());
          }
        } catch { /* Expired or invalid cached data is not displayed. */ }
        if (!fallback) {
          options.onState?.({ error: ui.snapshot.unavailable });
          throw error;
        }
        memory = { snapshot: fallback, cached: true, checkedAt: now() };
      } finally { clearTimeout(timeout); }
      options.onState?.(memory!);
      return memory!;
    })().finally(() => { pending = undefined; });
    return pending;
  };
  return async (input: RequestInfo | URL, init?: RequestInit) => {
    const request = input instanceof Request ? input : undefined;
    const url = new URL(request?.url || String(input), options.origin);
    const prefix = ['/api/v1/', `${base}api/v1/`].find(p => url.pathname.startsWith(p));
    if (url.origin !== options.origin || !prefix) return nativeFetch(input, init);
    if ((init?.method || request?.method || 'GET').toUpperCase() !== 'GET') return json({ detail: 'Snapshot mode is read-only.' }, 405);
    const signal = init?.signal || request?.signal;
    if (signal?.aborted) throw new DOMException('Aborted', 'AbortError');
    const loaded = await abortable(load(), signal);
    return querySnapshot(loaded.snapshot, url.pathname.slice(prefix.length).replace(/\/$/, ''), url.searchParams, loaded.cached);
  };
}

export function installSnapshotTransport(basePath: string): void {
  const banner = document.createElement('aside');
  banner.className = 'snapshot-banner'; banner.setAttribute('role', 'status'); banner.setAttribute('aria-live', 'polite');
  const status = document.createElement('span');
  status.textContent = ui.snapshot.loading;
  const refresh = document.createElement('button');
  refresh.type = 'button'; refresh.textContent = ui.snapshot.refresh;
  refresh.addEventListener('click', () => window.location.reload());
  banner.append(status, refresh); document.body.insertBefore(banner, document.getElementById('app'));
  let last: Loaded | { error: string } | undefined;
  const paint = () => {
    if (!last) return;
    if ('error' in last) { status.textContent = last.error; banner.dataset.stale = 'true'; return; }
    const { snapshot, cached } = last;
    const stale = cached || Date.now() - Date.parse(snapshot.generated_at) > 2 * 3600000;
    banner.dataset.stale = String(stale);
    status.textContent = ui.snapshot.summary(
      cached ? ui.snapshot.cached : stale ? ui.snapshot.delayed : ui.snapshot.normal,
      formatDateTime(snapshot.generated_at), snapshot.health.healthy, snapshot.health.configured
    );
  };
  let storage: CacheStorage | undefined;
  try { storage = window.caches; } catch { /* Private browsing can deny storage. */ }
  window.fetch = createSnapshotFetch(window.fetch.bind(window), {
    origin: window.location.origin, basePath, storage, onState: value => { last = value; paint(); },
  });
  window.setInterval(paint, 60000);
}
