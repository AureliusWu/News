import type {Snapshot} from './transport';

export function expandCompact(value: unknown): unknown {
  const envelope = value as {wire_schema_version?: number; snapshot?: Snapshot};
  const snapshot = envelope?.snapshot;
  if (envelope?.wire_schema_version !== 1 || !snapshot || !Array.isArray(snapshot.sources)
      || !Array.isArray(snapshot.articles) || snapshot.articles.length > 5000
      || new Set(snapshot.sources.map(source => source.slug)).size !== snapshot.sources.length)
    throw new Error('Unsupported compact news format.');
  return {...snapshot, articles: snapshot.articles.map(value => {
    const article = value as unknown as Record<string, unknown>;
    const {source_index, ...fields} = article;
    if (!Number.isInteger(source_index) || (source_index as number) < 0
        || (source_index as number) >= snapshot.sources.length || 'source' in fields)
      throw new Error('Invalid compact source reference.');
    return {...fields, source: snapshot.sources[source_index as number]};
  })};
}

export function expandHomePreview(value: unknown) {
  const envelope = value as {view?: string; total_articles?: number};
  const snapshot = expandCompact(value) as Snapshot;
  const total = envelope.total_articles;
  if (envelope.view !== 'home-preview-v1' || !Number.isSafeInteger(total) || (total as number) < 1
      || (total as number) > 5000 || snapshot.meta?.article_count !== total
      || snapshot.articles.length !== Math.min(30, total as number)) throw new Error('Invalid home preview coverage.');
  // Internal subset is explicit; public total and full generation remain separately bound.
  return {snapshot:{...snapshot,meta:{...snapshot.meta,article_count:snapshot.articles.length}},total:total as number};
}
