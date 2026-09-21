import type {NewsFilters, NewsMeta, NewsPage, NewsSource} from "../types/news";

const configuredBase = (import.meta.env.VITE_API_BASE_URL || "").trim().replace(/\/+$/, "");
export function resolveApiEndpoint(path: string): string {
  // BASE_URL locates static assets. API origin is a separate deployment setting.
  return configuredBase + "/api/v1/" + path.replace(/^\/+/, "");
}
export const resolveHealthEndpoint = () => resolveApiEndpoint("health");

export interface HealthInfo {
  status: string; app_name: string; app_version: string; environment: string;
  database_connected: boolean; checked_at: string;
}

async function request(path: string, signal?: AbortSignal): Promise<Response> {
  const response = await fetch(resolveApiEndpoint(path), {
    signal: signal ? AbortSignal.any([signal, AbortSignal.timeout(12000)]) : AbortSignal.timeout(12000),
    headers: {Accept: "application/json"}
  });
  if (!response.ok) throw new Error("News service returned HTTP " + response.status);
  if (!response.headers.get("content-type")?.includes("application/json")) throw new Error("News service returned an invalid response");
  return response;
}
export async function getHealth(): Promise<HealthInfo> {
  return (await request("health")).json();
}
export async function getMeta(): Promise<NewsMeta> {
  return (await request("meta")).json();
}
export async function getSources(): Promise<NewsSource[]> {
  return (await request("sources")).json();
}
export async function getNews(filters: NewsFilters, cursor: string | null, signal?: AbortSignal) {
  const params = new URLSearchParams({limit: "30"});
  for (const [key, value] of Object.entries(filters)) if (value.trim()) params.set(key, value.trim());
  if (cursor) params.set("cursor", cursor);
  const response = await request("news?" + params.toString(), signal);
  const page = await response.json() as NewsPage;
  if (!Array.isArray(page.items) || typeof page.has_more !== "boolean" ||
      (page.has_more && typeof page.next_cursor !== "string")) throw new Error("Invalid news page");
  const generated = response.headers.get("x-news-generated-at");
  const stale = response.headers.get("x-news-cache") === "hit" ||
    (generated !== null && Date.now() - Date.parse(generated) > 120000);
  return {page, stale};
}