export function isRecoveryRef(version, ref) {
  return /^\d+\.\d+\.\d+$/.test(version) && (ref === `v${version}` ||
    new RegExp(`^v${version.replaceAll('.','\\.')}-(?:rc|alpha)\\.\\d+$`).test(ref));
}

export function shouldRecover(row, {version, revision, now, lastAttempt = 0, publisherBusy = false}) {
  return !publisherBusy && Number.isFinite(now) && now - lastAttempt >= 3600000 &&
    row?.base_url === 'https://aureliuswu.github.io/News/' &&
    row.release?.version === version && row.release?.source_revision === revision &&
    Number.isFinite(Date.parse(row.observed_at)) && Math.abs(now - Date.parse(row.observed_at)) < 300000 &&
    (Boolean(row.transport_error) || row.source_health?.same_generation !== true ||
      row.snapshot?.collector_gate_pass !== true || !Number.isFinite(row.snapshot?.age_hours) || row.snapshot.age_hours >= 1);
}
