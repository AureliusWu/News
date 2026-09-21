export interface NewsSource {
  id: number; slug: string; name: string; publisher: string; homepage: string;
  country: string; region: string; language: string; category: string;
  source_type: string; health_status: string; enabled: boolean;
}
export interface NewsArticle {
  id: number; title: string; summary: string | null; url: string; image_url: string | null;
  source: NewsSource; published_at: string; region: string; category: string; language: string;
}
export interface NewsPage { items: NewsArticle[]; next_cursor: string | null; has_more: boolean }
export interface NewsMeta {
  version: string; regions: string[]; categories: string[]; languages: string[];
  source_count: number; article_count: number; last_sync_at: string | null;
}
export interface NewsFilters { region: string; category: string; language: string; source: string; q: string }