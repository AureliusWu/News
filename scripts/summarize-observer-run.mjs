import {appendFileSync, existsSync, readFileSync, readdirSync} from 'node:fs';
import {resolve} from 'node:path';
import {fileURLToPath} from 'node:url';

const PUBLIC_URL = 'https://aureliuswu.github.io/News/';
const MAX_OBSERVATION_BYTES = 256 * 1024;

export function classifyPublicSample(row, {version, revision}) {
  if (!row || row.transport_error || row.html?.status !== 200 || row.snapshot?.status !== 200) {
    return {status: 'UNAVAILABLE', detail: 'No complete public HTTP sample.'};
  }
  if (row.base_url !== PUBLIC_URL || row.release?.version !== version || row.release?.source_revision !== revision) {
    return {status: 'UNBOUND', detail: 'The sample does not match the pinned public application version and source.'};
  }
  const snapshot = row.snapshot;
  if (row.schema_version !== 1 || row.html.language_zh_cn !== true ||
      (snapshot.schema_version !== undefined && snapshot.schema_version !== 1) ||
      snapshot.collector_gate_pass !== true || row.source_health?.same_generation !== true ||
      !Number.isFinite(snapshot.age_hours) || typeof snapshot.freshness_2h_pass !== 'boolean') {
    return {status: 'INVALID', detail: 'The sample clock, schema, collector gate or source report binding is invalid.'};
  }
  if (snapshot.freshness_2h_pass) {
    return {status: 'FRESH', detail: 'The current bound snapshot meets the existing two-hour freshness rule.'};
  }
  if (snapshot.age_hours < 0) {
    return {status: 'INVALID', detail: 'The snapshot timestamp is outside the accepted future-clock tolerance.'};
  }
  return {status: 'STALE', detail: 'The current bound snapshot exceeds the existing two-hour freshness limit.'};
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
    '- Snapshot age: ' + hours(row?.snapshot?.age_hours)
  ];
  const schedule = row?.scheduling;
  if (schedule && !schedule.error) {
    lines.push('- Hours since the latest recorded scheduled Pages run: ' + hours(schedule.hours_since_last_run));
    lines.push('- Longest observed gap between scheduled Pages runs in the sampled seven-day window: ' + hours(schedule.max_interval_hours));
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
  const row = readLatestSample(directory);
  const assessment = classifyPublicSample(row, {version, revision});
  const summary = formatObserverSummary(row, assessment);
  if (summaryPath) appendFileSync(summaryPath, summary);
  console.log(summary.trimEnd());
  if (assessment.status !== 'FRESH') {
    console.log('::warning title=News public snapshot ' + assessment.status + '::' +
      assessment.detail + ' Snapshot age: ' + hours(row?.snapshot?.age_hours) + '.');
  }
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) main();
