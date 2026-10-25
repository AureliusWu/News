export function validateReleaseCandidate(version, candidate) {
  if (candidate?.schema_version !== 1 || candidate.version !== version || candidate.status !== 'CANDIDATE'
      || typeof candidate.plan !== 'string' || !candidate.plan.startsWith('docs/'))
    throw new Error('Candidate declaration must explicitly match this version and cannot grant a formal release.');
  return true;
}

export function validateReleaseApproval(version, approval) {
  if (!/^\d+\.\d+\.\d+$/.test(version)) return null;
  if (approval?.approval === 'verified-release') {
    const required = ['regression','source_integrity','performance','freshness','upgrade','devices','rollback','public_smoke'];
    if (approval.schema_version !== 1 || approval.version !== version || !/^[a-f0-9]{40}$/.test(approval.source_revision || '')
        || !Array.isArray(approval.gates) || approval.gates.length !== required.length
        || !required.every(id => approval.gates.filter(gate => gate.id === id && gate.status === 'PASS'
          && gate.source_revision === approval.source_revision && gate.version === version
          && Array.isArray(gate.evidence) && gate.evidence.length > 0).length === 1)
        || !Array.isArray(approval.waivers) || approval.waivers.length)
      throw new Error('Verified release requires every version/source-bound gate and no unresolved waivers.');
    return approval;
  }
  if (approval?.schema_version !== 1 || approval.version !== version ||
      approval.approval !== 'owner-approved-release-with-warnings' ||
      approval.accepted_by !== 'repository-owner' ||
      !/^\d{4}-\d{2}-\d{2}$/.test(approval.accepted_on || '') ||
      !approval.authorization_source || !Array.isArray(approval.waivers) || !approval.waivers.length) {
    throw new Error('Stable release requires its own explicit owner-approved waiver record.');
  }
  const ids = new Set();
  for (const waiver of approval.waivers) {
    if (!waiver.id || ids.has(waiver.id) || waiver.disposition !== 'WAIVED_FOR_THIS_RELEASE' ||
        !['FAIL', 'PARTIAL', 'NOT_RUN', 'NOT_PASSED'].includes(waiver.observed_status) ||
        !waiver.limitation || !Array.isArray(waiver.evidence) || !waiver.evidence.length) {
      throw new Error('Waivers must be unique, evidenced, and must not claim a passing result.');
    }
    ids.add(waiver.id);
  }
  return approval;
}
