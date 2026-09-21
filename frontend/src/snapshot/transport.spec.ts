import { describe, expect, it, vi } from 'vitest';
import { createSnapshotFetch, querySnapshot, validateSnapshot, type Snapshot } from './transport';

const NOW = Date.parse('2026-09-21T06:00:00Z');
function fixture(): Snapshot {
  const source = { id: 1, slug: 'sample', name: 'Sample', publisher: 'Sample', homepage: 'https://example.org', country: 'JP', region: 'japan', language: 'ja', category: 'world', source_type: 'official_rss', health_status: 'ok', enabled: true };
  return {
    schema_version: 1, generated_at: '2026-09-21T05:30:00Z', content_sha256: 'a'.repeat(64),
    sources: [source], articles: [1, 2, 3].map(id => ({ id, title: `Story ${id}`, summary: id === 2 ? 'A literal 100% match' : 'News summary', url: `https://example.org/story/${id}`, image_url: null, source, region: 'japan', category: 'world', language: 'ja', published_at: '2026-09-21T05:00:00Z' })),
    meta: { version: '0.2.0', regions: ['japan'], categories: ['world'], languages: ['ja'], source_count: 1, article_count: 3, last_sync_at: '2026-09-21T05:30:00Z', publication_mode: 'snapshot' },
    health: { configured: 1, healthy: 1, failed: 0, gate_pass: true },
  };
}
describe('snapshot query contract', () => {
  it('accepts a valid snapshot', () => expect(validateSnapshot(fixture(), NOW).articles).toHaveLength(3));
  it('rejects an expired snapshot', () => expect(() => validateSnapshot(fixture(), NOW + 73 * 3600000)).toThrow());
  it('rejects a future snapshot', () => expect(() => validateSnapshot(fixture(), NOW - 3600000)).toThrow());
  it('rejects unsafe article links', () => { const s = fixture(); s.articles[0].url = 'javascript:alert(1)'; expect(() => validateSnapshot(s, NOW)).toThrow(); });
  it('rejects duplicate identities', () => { const s = fixture(); s.articles[1].id = 1; expect(() => validateSnapshot(s, NOW)).toThrow(); });
  it('filters region, language, category and source together', async () => {
    expect((await querySnapshot(fixture(), 'news', new URLSearchParams('region=japan&language=ja&category=world&source=sample')).json()).items).toHaveLength(3);
    expect((await querySnapshot(fixture(), 'news', new URLSearchParams('region=africa')).json()).items).toEqual([]);
  });
  it('treats search as literal text', async () => expect((await querySnapshot(fixture(), 'news', new URLSearchParams('q=100%25')).json()).items.map((a: {id:number}) => a.id)).toEqual([2]));
  it('paginates without overlaps and terminates', async () => {
    const a = await querySnapshot(fixture(), 'news', new URLSearchParams('limit=2')).json();
    const b = await querySnapshot(fixture(), 'news', new URLSearchParams({ limit: '2', cursor: a.next_cursor })).json();
    expect([...a.items, ...b.items].map(x => x.id)).toEqual([1, 2, 3]); expect(b.has_more).toBe(false); expect(b.next_cursor).toBeNull();
  });
  it('rejects malformed and filter-mismatched cursors', async () => {
    expect(querySnapshot(fixture(), 'news', new URLSearchParams('cursor=invalid')).status).toBe(400);
    const a = await querySnapshot(fixture(), 'news', new URLSearchParams('limit=1')).json();
    expect(querySnapshot(fixture(), 'news', new URLSearchParams({ cursor: a.next_cursor, q: 'changed' })).status).toBe(400);
  });
  it('rejects mixed snapshot generations', async () => {
    const a = await querySnapshot(fixture(), 'news', new URLSearchParams('limit=1')).json();
    const s = fixture(); s.content_sha256 = 'b'.repeat(64);
    expect(querySnapshot(s, 'news', new URLSearchParams({ cursor: a.next_cursor })).status).toBe(409);
  });
  it('validates page size', () => expect(querySnapshot(fixture(), 'news', new URLSearchParams('limit=0')).status).toBe(422));
  it('reports snapshot health instead of a fake live database', async () => expect(await querySnapshot(fixture(), 'health', new URLSearchParams()).json()).toMatchObject({ status: 'snapshot', database: 'not_applicable' }));
});
describe('snapshot transport isolation', () => {
  const options = { origin: 'https://example.org', basePath: '/News/', now: () => NOW };
  it('downloads from the project base and shares concurrent downloads', async () => {
    const fetcher = vi.fn(async (_input: RequestInfo | URL, _init?: RequestInit) => new Response(JSON.stringify(fixture())));
    const adapted = createSnapshotFetch(fetcher as typeof fetch, options);
    await Promise.all([adapted('/api/v1/news'), adapted('/News/api/v1/meta')]);
    expect(fetcher).toHaveBeenCalledTimes(1); expect(fetcher.mock.calls[0][0]).toBe('https://example.org/News/data/news.json');
  });
  it('does not intercept other origins or unrelated assets', async () => {
    const fetcher = vi.fn(async () => new Response('passthrough'));
    const adapted = createSnapshotFetch(fetcher as typeof fetch, options);
    expect(await (await adapted('https://other.example.org/api/v1/news')).text()).toBe('passthrough');
    expect(await (await adapted('/assets/icon.svg')).text()).toBe('passthrough'); expect(fetcher).toHaveBeenCalledTimes(2);
  });
  it('rejects writes without fetching', async () => {
    const fetcher = vi.fn(); const adapted = createSnapshotFetch(fetcher, options);
    expect((await adapted('/api/v1/news', { method: 'POST' })).status).toBe(405); expect(fetcher).not.toHaveBeenCalled();
  });
  it('respects an already aborted caller', async () => {
    const controller = new AbortController(); controller.abort();
    const adapted = createSnapshotFetch(vi.fn(), options);
    await expect(adapted('/api/v1/news', { signal: controller.signal })).rejects.toMatchObject({ name: 'AbortError' });
  });
  it('uses a validated cache on network failure and labels it stale', async () => {
    const onState = vi.fn();
    const storage = { open: async () => ({ match: async () => new Response(JSON.stringify(fixture())) }) } as unknown as CacheStorage;
    const adapted = createSnapshotFetch(vi.fn(async () => { throw new Error('offline'); }), { ...options, storage, onState });
    const response = await adapted('/api/v1/news');
    expect(response.headers.get('X-Cache-Stale')).toBe('true'); expect(onState.mock.calls[0][0].cached).toBe(true);
  });
  it('does not fabricate empty news when offline without a cache', async () => {
    const adapted = createSnapshotFetch(vi.fn(async () => { throw new Error('offline'); }), options);
    await expect(adapted('/api/v1/news')).rejects.toThrow('offline');
  });
});
