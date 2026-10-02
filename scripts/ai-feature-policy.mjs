import {readFileSync} from 'node:fs';

export function validateAiPolicy(policy) {
  if (!policy || policy.schema_version !== 1 || policy.scope !== 'content-generation' ||
      policy.enabled !== false || policy.translation_enabled !== false || policy.summary_enabled !== false ||
      policy.disabled_reason !== 'no-verified-free-quota' || policy.max_cost_usd !== 0 ||
      policy.max_requests_per_day !== 0 || policy.max_cache_entries !== 0 ||
      policy.source_citations_required !== true || policy.original_switch_required !== true ||
      policy.external_content_is_untrusted !== true) {
    throw new Error('AI content generation must remain disabled with zero cost and request budgets. Enabling it requires a separately approved and verified implementation.');
  }
  const allowed = new Set(['schema_version', 'scope', 'enabled', 'translation_enabled', 'summary_enabled',
    'disabled_reason', 'max_cost_usd', 'max_requests_per_day', 'max_cache_entries',
    'source_citations_required', 'original_switch_required', 'external_content_is_untrusted']);
  if (Object.keys(policy).some(key => !allowed.has(key))) throw new Error('Unexpected AI policy field. Never place credentials in release metadata.');
  return Object.freeze({...policy});
}

export function readAiPolicy(root = new URL('../', import.meta.url)) {
  return validateAiPolicy(JSON.parse(readFileSync(new URL('backend/config/ai_features.json', root), 'utf8')));
}
