export interface NewsEvent {
  event_id: string; title: string; language: string;
  first_published_at: string; last_published_at: string;
  article_ids: string[]; publisher_ids: string[]; publisher_count: number;
  article_count: number; source_names: string[];
}
export interface EventIndex {
  schema_version: 1; snapshot_id: string; generated_at: string; content_sha256: string;
  method_version: string; acceptance_status: string; events: NewsEvent[];
  matcher_version?: string; aliases?: Record<string, string>;
}
