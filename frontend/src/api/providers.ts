import {createSnapshotFetch, installSnapshotTransport, validateSnapshot, type Snapshot} from "../snapshot/transport";

export interface NewsProvider {
  mode: "api" | "snapshot";
  request(path: string, signal?: AbortSignal): Promise<Response>;
  snapshot(signal?: AbortSignal): Promise<Snapshot>;
  asset(snapshot: Snapshot, name: string, signal?: AbortSignal): Promise<unknown>;
}
function checked(response: Response) {
  if (!response.ok) throw new Error("News service returned HTTP " + response.status);
  if (!response.headers.get("content-type")?.includes("application/json")) throw new Error("News service returned an invalid response");
  return response;
}
function timeout(signal?: AbortSignal) {
  return signal ? AbortSignal.any([signal, AbortSignal.timeout(12000)]) : AbortSignal.timeout(12000);
}
export class ApiProvider implements NewsProvider {
  readonly mode = "api" as const;
  constructor(private base = "") {}
  async request(path: string, signal?: AbortSignal) {
    return checked(await fetch(this.base + "/api/v1/" + path.replace(/^\/+/, ""), {signal: timeout(signal), headers: {Accept: "application/json"}}));
  }
  async snapshot(signal?: AbortSignal): Promise<Snapshot> { return validateSnapshot(await (await this.request("snapshot", signal)).json()); }
  async asset(snapshot: Snapshot, name: string, signal?: AbortSignal): Promise<unknown> {
    if (!snapshot.snapshot_id || !/^[a-f0-9]{24}$/.test(snapshot.snapshot_id)
        || !new RegExp(`^(events|source-health)\\.${snapshot.snapshot_id}\\.json$`).test(name)) {
      throw new Error("快照未提供兼容的版本化报告。");
    }
    const raw = await (await this.request(`snapshots/${snapshot.snapshot_id}/${name}`, signal)).text();
    if (raw.length > 4 * 1024 * 1024) throw new Error("报告超出大小限制。");
    const value = JSON.parse(raw);
    if (value.snapshot_id !== snapshot.snapshot_id || value.generated_at !== snapshot.generated_at
        || value.content_sha256 !== snapshot.content_sha256) throw new Error("报告与新闻快照不属于同一版本，请刷新后重试。");
    return value;
  }
}
export class SnapshotProvider implements NewsProvider {
  readonly mode = "snapshot" as const;
  constructor(private scopedFetch: typeof fetch, private nativeFetch: typeof fetch, private origin: string,
              private base: string, private storage?: CacheStorage) {}
  async request(path: string, signal?: AbortSignal) {
    return checked(await this.scopedFetch(new URL("/api/v1/" + path.replace(/^\/+/, ""), this.origin).href, {signal: timeout(signal), headers: {Accept: "application/json"}}));
  }
  async snapshot(signal?: AbortSignal) { return validateSnapshot(await (await this.request("snapshot", signal)).json()); }
  async asset(snapshot: Snapshot, name: string, signal?: AbortSignal) {
    if (!snapshot.snapshot_id || !/^[a-f0-9]{24}$/.test(snapshot.snapshot_id)
        || !new RegExp(`^(events|source-health)\\.${snapshot.snapshot_id}\\.json$`).test(name)) {
      throw new Error("快照未提供兼容的版本化报告。");
    }
    const url = new URL(`${this.base}data/${name}`, this.origin).href;
    let cache: Cache | undefined;
    try { cache = await this.storage?.open(`global-news-reports-v1:${this.base}`); } catch { /* Optional storage. */ }
    let response: Response;
    try {
      response = checked(await this.nativeFetch(url, {cache: "no-store", credentials: "omit", signal: timeout(signal)}));
    } catch (error) {
      if (signal?.aborted) throw error;
      const saved = await cache?.match(url);
      if (!saved) throw error;
      response = saved;
    }
    const raw = await response.text();
    if (raw.length > 4 * 1024 * 1024) throw new Error("报告超出大小限制。");
    const value = JSON.parse(raw);
    if (value.snapshot_id !== snapshot.snapshot_id || value.generated_at && value.generated_at !== snapshot.generated_at
        || value.content_sha256 && value.content_sha256 !== snapshot.content_sha256) throw new Error("报告与新闻快照不属于同一版本，请刷新后重试。");
    try {
      await cache?.put(url, new Response(raw, {headers: {"content-type": "application/json"}}));
      const keys = await cache?.keys();
      for (const old of (keys || []).slice(0, Math.max(0, (keys?.length || 0) - 6))) await cache?.delete(old);
    } catch { /* A full cache cannot block online reading. */ }
    return value;
  }
}
export function createSnapshotProvider(nativeFetch: typeof fetch, options: Parameters<typeof createSnapshotFetch>[1]) {
  return new SnapshotProvider(createSnapshotFetch(nativeFetch, options), nativeFetch, options.origin, options.basePath, options.storage);
}
let provider: NewsProvider | undefined;
export function getProvider(): NewsProvider {
  if (!provider) {
    if (import.meta.env.VITE_NEWS_MODE === "snapshot") {
      let storage: CacheStorage | undefined;
      try { storage = window.caches; } catch { /* Optional storage. */ }
      const nativeFetch = window.fetch.bind(window);
      provider = new SnapshotProvider(installSnapshotTransport(import.meta.env.BASE_URL, false), nativeFetch,
        window.location.origin, import.meta.env.BASE_URL, storage);
    } else provider = new ApiProvider((import.meta.env.VITE_API_BASE_URL || "").trim().replace(/\/+$/, ""));
  }
  return provider;
}
