import {appendFileSync, existsSync, readFileSync, readdirSync} from 'node:fs';
import {resolve} from 'node:path';
import {fileURLToPath} from 'node:url';
import {snapshotFreshness} from './freshness-gate.mjs';

const PUBLIC_URL = 'https://aureliuswu.github.io/News/';
const MAX_OBSERVATION_BYTES = 256 * 1024;

export function classifyPublicSample(row, {version, revision}) {
  const freshness = snapshotFreshness(Date.parse(row?.observed_at), row?.snapshot?.generated_at);
  const result = (status, detail) => ({status, detail, ageHours: freshness.ageHours});
  if (!row || row.transport_error || row.html?.status !== 200 || row.snapshot?.status !== 200) {
    return result('UNAVAILABLE', 'No complete public HTTP sample.');
  }
  if (row.base_url !== PUBLIC_URL || row.release?.version !== version || row.release?.source_revision !== revision) {
    return result('UNBOUND', 'The sample does not match the pinned public application version and source.');
  }
  const snapshot = row.snapshot;
  if (row.schema_version !== 1 || row.html.language_zh_cn !== true ||
      (snapshot.schema_version !== undefined && snapshot.schema_version !== 1) ||
      snapshot.collector_gate_pass !== true || row.source_health?.same_generation !== true) {
    return result('INVALID', 'The sample schema, collector gate or source report binding is invalid.');
  }
  if (freshness.status === 'FRESH') {
    return result('FRESH', 'The current bound snapshot meets the existing two-hour freshness rule.');
  }
  if (freshness.status === 'INVALID') {
    return result('INVALID', 'The snapshot clock is missing, invalid or outside the accepted future-clock tolerance.');
  }
  return result('STALE', 'The current bound snapshot exceeds the existing two-hour freshness limit.');
}

function readLatestSample(directory) {
  if (!existsSync(directory)) return null;
  const name = readdirSync(directory)
    .filter(name => /^\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}\.\d{3}Z\.json$/.test(name))
    .sort().at(-1);
  if (!name) return null;
  const bytes = readFileSync(resolve(directory, name));
  if (bytes.length > MAX_OBSERVATION_BYTES) throw new Error('Latest raw observation exceeds its size bound.');
  return JSON.parse(bytes);
}

function hours(value) {
  return Number.isFinite(value) ? value.toFixed(2) + ' h' : 'unavailable';
}

export function formatObserverSummary(row, assessment) {
  const lines = [
    '### Latest public News snapshot',
    '',
    '**' + assessment.status + '** — ' + assessment.detail,
    '',
    '- Snapshot age: ' + hours(assessment.ageHours)
  ];
  const schedule = row?.scheduling;
  if (schedule && !schedule.error) {
    if (schedule.run_count_7d === 0) {
      lines.push('- No scheduled Pages runs were recorded in the sampled seven-day window.');
    } else {
      lines.push('- Hours since the latest recorded scheduled Pages run: ' + hours(schedule.hours_since_last_run));
      lines.push('- Longest observed gap between scheduled Pages runs in the sampled seven-day window: ' + hours(schedule.max_interval_hours));
    }
    if (schedule.history_capped) lines.push('- The Actions query reached its run limit; older runs may be absent.');
  } else {
    lines.push('- Scheduled Pages run history was unavailable in this sample.');
  }
  lines.push('', 'This sample is separate from seven-day coverage and formal release acceptance.', '');
  return lines.join('\n') + '\n';
}

function main() {
  const {OBSERVER_VERSION: version, OBSERVER_REVISION: revision, GITHUB_STEP_SUMMARY: summaryPath} = process.env;
  if (!version || !/^[0-9a-f]{40}$/.test(revision ?? '')) throw new Error('Observer requires a pinned version and full application SHA.');
  const directory = resolve(process.argv[2] || 'artifacts/v1-cloud-observer/incoming');
  let row, assessment;
  try {
    row = readLatestSample(directory);
    assessment = classifyPublicSample(row, {version, revision});
  } catch {
    assessment = {status: 'INVALID', detail: 'The latest raw observation could not be read. Inspect the original artifact.'};
  }
  const summary = formatObserverSummary(row, assessment);
  if (summaryPath) appendFileSync(summaryPath, summary);
  console.log(summary.trimEnd());
  if (assessment.status !== 'FRESH') {
    console.log('::warning title=News public snapshot ' + assessment.status + '::' +
      assessment.detail + ' Snapshot age: ' + hours(assessment.ageHours) + '.');
  }
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) main();
