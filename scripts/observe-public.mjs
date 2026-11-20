import {mkdirSync, writeFileSync} from 'node:fs';
import {execFileSync} from 'node:child_process';
import {resolve} from 'node:path';
import {fileURLToPath} from 'node:url';
import {snapshotFreshness} from './freshness-gate.mjs';
import {isSnapshotPair} from './snapshot-pair.mjs';

const base = new URL('https://aureliuswu.github.io/News/');
const WINDOW_MS = 7 * 86400000;
const MAX_SCHEDULE_RUNS = 400;

async function getPublicResource(path, optional = false) {
  const start = performance.now();
  const response = await fetch(new URL(path, base), {cache: 'no-store', signal: AbortSignal.timeout(25000)});
  const body = await response.text();
  if (Buffer.byteLength(body) > 8 * 1024 * 1024) throw new Error(path + ': oversized response');
  if (!response.ok && !(optional && response.status === 404)) throw new Error(path + ': HTTP ' + response.status);
  return {status: response.status, elapsed_ms: Math.round(performance.now() - start), bytes: Buffer.byteLength(body), body};
}

function listScheduledRuns(since) {
  return JSON.parse(execFileSync('gh', [
    'run', 'list', '--repo', 'AureliusWu/News', '--workflow', 'deploy-gh-pages.yml',
    '--branch', 'main', '--event', 'schedule', '--created', '>=' + since, '--limit', String(MAX_SCHEDULE_RUNS),
    '--json', 'databaseId,conclusion,event,createdAt,updatedAt,headSha'
  ], {encoding: 'utf8', timeout: 30000}));
}

export function summarizeScheduledRuns(history, observedAtMs) {
  const unique = new Map();
  for (const run of history) {
    const time = Date.parse(run.createdAt);
    if (run.event === 'schedule' && Number.isSafeInteger(run.databaseId) &&
        time >= observedAtMs - WINDOW_MS && time <= observedAtMs) {
      unique.set(run.databaseId, {run, time});
    }
  }
  const runs = [...unique.values()].sort((a, b) => a.time - b.time);
  const gaps = runs.slice(1).map((entry, index) => (entry.time - runs[index].time) / 3600000);
  const latest = runs.at(-1);
  return {
    run_count_7d: runs.length,
    intervals_hours: gaps,
    max_interval_hours: gaps.length ? Math.max(...gaps) : null,
    latest_run_id: latest?.run.databaseId ?? null,
    latest_run_at: latest?.run.createdAt ?? null,
    hours_since_last_run: latest ? (observedAtMs - latest.time) / 3600000 : null,
    history_capped: history.length >= MAX_SCHEDULE_RUNS,
    caveat: 'Run intervals are not independent snapshot-age observations and do not establish seven-day freshness.',
    error: null
  };
}

export async function observePublic(observedAt, {get = getPublicResource, listRuns = listScheduledRuns} = {}) {
  const observedAtMs = observedAt.getTime();
  const observation = {
    schema_version: 1,
    observed_at: observedAt.toISOString(),
    base_url: base.href,
    acceptance: {seven_day_gate: 'NOT_EVALUATED', browser_gate: 'NOT_EVALUATED', physical_device_gate: 'NOT_EVALUATED'}
  };
  try {
    // Identify the deployed application even when a subsequent resource fails.
    const releaseResponse = await get('release.json', true);
    const release = releaseResponse.status === 200 ? JSON.parse(releaseResponse.body) : null;
    observation.release = {status: releaseResponse.status, version: release?.version ?? null,
      source_revision: release?.source_revision ?? null, formal_release: release?.formal_release ?? null};
    const html = await get('');
    observation.html = {status: html.status, elapsed_ms: html.elapsed_ms, language_zh_cn: /lang=["']zh-CN["']/.test(html.body),
      scripts: [...html.body.matchAll(/assets\/[^"' ]+\.js/g)].map(match => match[0])};
    const news = await get('data/news.json');
    const data = JSON.parse(news.body);
    const freshness = snapshotFreshness(observedAtMs, data.generated_at);
    observation.snapshot = {status: news.status, elapsed_ms: news.elapsed_ms, bytes: news.bytes,
      generated_at: data.generated_at, snapshot_id: data.snapshot_id, schema_version: data.schema_version, version: data.meta?.version,
      content_sha256: data.content_sha256, article_count: data.articles?.length, age_hours: freshness.ageHours,
      freshness_2h_pass: freshness.status === 'FRESH', collector_gate_pass: data.health?.gate_pass === true};
    const healthFile = data.source_health_file;
    if (healthFile && healthFile !== 'source-health.' + data.snapshot_id + '.json') {
      throw new Error('Invalid bound health filename');
    }
    const health = await get('data/' + (healthFile || 'source-health.json'));
    const sourceHealth = JSON.parse(health.body);
    observation.source_health = {checked_at: sourceHealth.checked_at, generated_at: sourceHealth.generated_at,
      snapshot_id: sourceHealth.snapshot_id, same_generation: isSnapshotPair(data, sourceHealth),
      summary: sourceHealth.summary ?? sourceHealth.health};
  } catch (error) {
    observation.transport_error = String(error.message).slice(0, 500);
  }
  try {
    const history = listRuns(new Date(observedAtMs - WINDOW_MS).toISOString());
    observation.scheduling = summarizeScheduledRuns(history, observedAtMs);
    observation.workflow_history = history;
  } catch (error) {
    observation.scheduling = {error: String(error.message).slice(0, 500)};
  }
  return observation;
}

async function main() {
  const observedAt = new Date();
  const observation = await observePublic(observedAt);
  const directory = resolve(process.argv[2] || 'artifacts/v1-observations');
  mkdirSync(directory, {recursive: true});
  const path = resolve(directory, observedAt.toISOString().replaceAll(':', '-') + '.json');
  writeFileSync(path, JSON.stringify(observation, null, 2) + '\n');
  const {html, snapshot, release, source_health, transport_error, scheduling} = observation;
  console.log(JSON.stringify({path, html, snapshot, release, source_health, transport_error,
    scheduling: {...scheduling, intervals_hours: undefined}}, null, 2));
  if (transport_error) process.exitCode = 1;
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) await main();
