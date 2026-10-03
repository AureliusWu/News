// The report binds to the snapshot through snapshot_id and checked_at.
// generated_at and content_sha256 are snapshot fields, not report fields.
export function isSnapshotPair(news, health) {
  if (!news || !health || typeof news !== 'object' || typeof health !== 'object'
      || Array.isArray(news) || Array.isArray(health)
      || typeof news.generated_at !== 'string' || !Number.isFinite(Date.parse(news.generated_at))
      || health.checked_at !== news.generated_at) return false;
  if (news.snapshot_id != null) {
    return typeof news.snapshot_id === 'string' && news.snapshot_id.length > 0
      && health.snapshot_id === news.snapshot_id;
  }
  return health.snapshot_id == null;
}
