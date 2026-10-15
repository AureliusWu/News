import {describe, expect, it, vi} from 'vitest';
import {createSnapshotProvider} from '../api/providers';
import type {Snapshot} from '../snapshot/transport';
import {warmSnapshotHome} from './warmup';

const NOW = Date.parse('2026-10-15T07:30:00Z');
const origin = 'https://example.org';
function fixture(): Snapshot {
  const source = {id: 1, slug: 'sample', name: 'Sample', publisher: 'Sample', homepage: origin,
    country: 'JP', region: 'japan', language: 'ja', category: 'world', source_type: 'official_rss', health_status: 'ok', enabled: true};
  return {
    schema_version: 1, generated_at: '2026-10-15T07:00:00Z', content_sha256: 'a'.repeat(64),
    sources: [source], articles: [{id: 1, title: 'Story 1', summary: null, url: origin + '/story/1', image_url: null,
      source, region: 'japan', category: 'world', language: 'ja', published_at: '2026-10-15T06:00:00Z'}],
    meta: {version: '0.4.0-alpha.1', regions: ['japan'], categories: ['world'], languages: ['ja'], source_count: 1,
      article_count: 1, last_sync_at: '2026-10-15T07:00:00Z', publication_mode: 'snapshot'},
    health: {configured: 1, healthy: 1, failed: 0, gate_pass: true},
  };
}

describe('homepage snapshot warmup', () => {
  it.each([['/', '/'], ['/News/', '/News/'], ['/News', '/News/']])(
    'shares a pending download with the page at %s', async (pathname, basePath) => {
      let finish!: (response: Response) => void;
      const download = new Promise<Response>(resolve => { finish = resolve; });
      const nativeFetch = vi.fn(async (_input: RequestInfo | URL, _init?: RequestInit) => (await download).clone());
      const provider = createSnapshotProvider(nativeFetch as typeof fetch, {origin, basePath, now: () => NOW});
      const warmed = warmSnapshotHome({mode: 'snapshot', pathname, basePath, resolveProvider: () => provider});
      const page = provider.request('news?limit=30');
      try {
        expect(nativeFetch).toHaveBeenCalledTimes(1);
        expect(nativeFetch.mock.calls[0]?.[0]).toBe(origin + basePath + 'data/news.json');
      } finally { finish(new Response(JSON.stringify(fixture()))); }
      await warmed;
      expect((await (await page).json()).items[0].title).toBe('Story 1');
      await provider.request('sources');
      expect(nativeFetch).toHaveBeenCalledTimes(1);
    },
  );

  it('does not create a provider or send requests in API mode', () => {
    const resolveProvider = vi.fn();
    expect(warmSnapshotHome({mode: 'api', pathname: '/News/', basePath: '/News/', resolveProvider})).toBeUndefined();
    expect(resolveProvider).not.toHaveBeenCalled();
  });

  it('keeps non-homepage routes lazy', () => {
    const resolveProvider = vi.fn();
    for (const pathname of ['/News/about', '/News/events', '/News/library', '/News/sources']) {
      expect(warmSnapshotHome({mode: 'snapshot', pathname, basePath: '/News/', resolveProvider})).toBeUndefined();
    }
    expect(resolveProvider).not.toHaveBeenCalled();
  });

  it('does not warm an API provider even if the caller supplies snapshot mode', () => {
    const request = vi.fn();
    warmSnapshotHome({mode: 'snapshot', pathname: '/News/', basePath: '/News/', resolveProvider: () => ({mode: 'api', request})});
    expect(request).not.toHaveBeenCalled();
  });

  it('leaves a failed warmup retryable by the normal page request', async () => {
    const nativeFetch = vi.fn(async () => { throw new Error('offline'); });
    const provider = createSnapshotProvider(nativeFetch, {origin, basePath: '/News/', now: () => NOW});
    await expect(warmSnapshotHome({mode: 'snapshot', pathname: '/News/', basePath: '/News/', resolveProvider: () => provider})).resolves.toBeUndefined();
    await expect(provider.request('news')).rejects.toThrow('offline');
    expect(nativeFetch).toHaveBeenCalledTimes(2);
  });

  it('does not interrupt startup when optional initialization throws', () => {
    const options = {mode: 'snapshot', pathname: '/News/', basePath: '/News/'};
    expect(() => warmSnapshotHome({...options, resolveProvider: () => { throw new Error('unavailable'); }})).not.toThrow();
    expect(() => warmSnapshotHome({...options, resolveProvider: () => ({mode: 'snapshot', request: () => { throw new Error('unavailable'); }})})).not.toThrow();
  });

  it('shares a validated stale fallback when the network is offline', async () => {
    const nativeFetch = vi.fn(async () => { throw new Error('offline'); });
    const storage = {open: async () => ({match: async () => new Response(JSON.stringify(fixture()))})} as unknown as CacheStorage;
    const provider = createSnapshotProvider(nativeFetch, {origin, basePath: '/News/', now: () => NOW, storage});
    await warmSnapshotHome({mode: 'snapshot', pathname: '/News/', basePath: '/News/', resolveProvider: () => provider});
    const response = await provider.request('news');
    expect(response.headers.get('X-Cache-Stale')).toBe('true');
    expect((await response.json()).items).toHaveLength(1);
    expect(nativeFetch).toHaveBeenCalledTimes(1);
  });
});
