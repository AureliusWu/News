import type {NewsFilters} from "../types/news";

export const FILTER_KEYS = ["q", "region", "category", "language", "source"] as const;
export function filtersFromQuery(query: Record<string, unknown>): NewsFilters {
  const result = {q: "", region: "", category: "", language: "", source: ""};
  for (const key of FILTER_KEYS) {
    const value = query[key];
    result[key] = typeof value === "string" ? value.trim().slice(0, key === "q" ? 200 : 100) : "";
  }
  return result;
}
export function queryFromFilters(filters: NewsFilters): Record<string, string> {
  const result: Record<string, string> = {};
  for (const key of FILTER_KEYS) if (filters[key].trim()) result[key] = filters[key].trim().slice(0, key === "q" ? 200 : 100);
  return result;
}
