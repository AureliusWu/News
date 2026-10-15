export function validateReleaseApproval(version, approval) {
  if (!/^\d+\.\d+\.\d+$/.test(version)) return null;
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
