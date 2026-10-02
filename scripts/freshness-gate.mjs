import {readdirSync, readFileSync, mkdirSync, writeFileSync, existsSync} from 'node:fs';
import {resolve, dirname} from 'node:path';
import {fileURLToPath} from 'node:url';

const SLOT_MS = 30 * 60 * 1000;
const WINDOW_MS = 7 * 86400000;
const EXPECTED_SLOTS = WINDOW_MS / SLOT_MS;
const MAX_RECORDS = 800;

export function compactObservation(row) {
  return {schema_version: 1, observed_at: row.observed_at, base_url: row.base_url,
    html: {status: row.html?.status, language_zh_cn: row.html?.language_zh_cn},
    snapshot: {status: row.snapshot?.status, generated_at: row.snapshot?.generated_at,
      collector_gate_pass: row.snapshot?.collector_gate_pass},
    source_health: {same_generation: row.source_health?.same_generation},
    release: {version: row.release?.version ?? null, source_revision: row.release?.source_revision ?? null},
    transport_error: row.transport_error ?? null};
}

export function evaluateFreshness(rows, {now = Date.now(), expectedVersion = null} = {}) {
  if (!Number.isFinite(now)) throw new Error('Invalid observation clock.');
  const end = Math.floor(now / SLOT_MS) * SLOT_MS;
  const start = end - WINDOW_MS;
  const accepted = rows.filter(row => row?.schema_version === 1 &&
    row.base_url === 'https://aureliuswu.github.io/News/' &&
    Number.isFinite(Date.parse(row.observed_at)) && Date.parse(row.observed_at) <= now &&
    (!expectedVersion || row.release?.version === expectedVersion));
  const span = accepted.length ? (Math.max(...accepted.map(r => Date.parse(r.observed_at))) -
    Math.min(...accepted.map(r => Date.parse(r.observed_at)))) / 3600000 : 0;
  const buckets = new Map();
  for (const row of accepted) {
    const time = Date.parse(row.observed_at);
    if (time < start || time >= end) continue;
    const slot = Math.floor((time - start) / SLOT_MS);
    const generated = Date.parse(row.snapshot?.generated_at);
    const age = time - generated;
    const good = !row.transport_error && row.html?.status === 200 && row.html?.language_zh_cn === true &&
      row.snapshot?.status === 200 && row.snapshot?.collector_gate_pass === true &&
      row.source_health?.same_generation === true && Number.isFinite(generated) &&
      age >= -5 * 60000 && age <= 2 * 3600000;
    // Multiple samples do not increase coverage; a failed sample cannot be hidden by a retry.
    buckets.set(slot, (buckets.get(slot) ?? true) && good);
  }
  const passed = [...buckets.values()].filter(Boolean).length;
  const ratio = passed / EXPECTED_SLOTS;
  const enoughSpan = span >= 168;
  const gatePass = enoughSpan && ratio >= 0.95;
  return {schema_version: 1, evaluated_at: new Date(now).toISOString(),
    window_start: new Date(start).toISOString(), window_end: new Date(end).toISOString(),
    expected_version: expectedVersion, interval_minutes: 30, expected_slots: EXPECTED_SLOTS,
    observed_slots: buckets.size, passing_slots: passed, failed_slots: buckets.size - passed,
    missing_slots: EXPECTED_SLOTS - buckets.size, passing_fraction: ratio, observation_span_hours: span,
    minimum_span_hours: 168, required_fraction: 0.95,
    status: !enoughSpan ? 'WARMING_UP' : gatePass ? 'PASS' : 'FAIL', gate_pass: gatePass,
    candidate_version_bound: Boolean(expectedVersion), formal_release: false,
    caveat: 'Direct HTTP observations only. Missing slots count as failures; Actions run success rates are not freshness evidence.'};
}

function main() {
  const args = process.argv.slice(2);
  const value = (name, fallback) => {const i = args.indexOf(name); return i < 0 ? fallback : args[i + 1];};
  const input = resolve(value('--input', 'artifacts/v1-observations'));
  const output = resolve(value('--output', 'artifacts/v1-freshness-report.json'));
  const historyPath = value('--history', null);
  const expectedVersion = value('--expected-version', null);
  let rows = [];
  if (historyPath && existsSync(historyPath)) {
    const bytes = readFileSync(historyPath);
    if (bytes.length > 512 * 1024) throw new Error('Observation history exceeds its bound.');
    const history = JSON.parse(bytes.toString('utf8'));
    if (history.schema_version !== 1 || !Array.isArray(history.observations) || history.observations.length > MAX_RECORDS)
      throw new Error('Invalid observation history; never silently reset it.');
    rows = history.observations;
  }
  if (existsSync(input)) {
    for (const name of readdirSync(input).filter(name => /^\d{4}-\d{2}-\d{2}T.*\.json$/.test(name))) {
      const bytes = readFileSync(resolve(input, name));
      if (bytes.length > 256 * 1024) throw new Error('Observation exceeds its bound.');
      rows.push(JSON.parse(bytes.toString('utf8')));
    }
  }
  const now = Date.now();
  const unique = new Map();
  for (const row of rows) {
    const time = Date.parse(row.observed_at);
    if (row.schema_version !== 1 || !Number.isFinite(time) || time > now)
      throw new Error('Invalid or future observation; never rewrite its timestamp.');
    if (time >= now - 8 * 86400000) {
      const normalized = compactObservation(row);
      const existing = unique.get(row.observed_at);
      if (existing && JSON.stringify(existing) !== JSON.stringify(normalized)) throw new Error('Conflicting observation timestamp.');
      unique.set(row.observed_at, normalized);
    }
  }
  rows = [...unique.values()].sort((a,b) => Date.parse(a.observed_at) - Date.parse(b.observed_at));
  if (rows.length > MAX_RECORDS) throw new Error('Observation count exceeds its bound.');
  if (historyPath) {
    const bytes = JSON.stringify({schema_version: 1, observations: rows});
    if (Buffer.byteLength(bytes) > 512 * 1024) throw new Error('Compacted observation history exceeds its bound.');
    mkdirSync(dirname(resolve(historyPath)), {recursive:true});
    writeFileSync(historyPath, bytes + '\n');
  }
  const report = evaluateFreshness(rows, {now, expectedVersion});
  mkdirSync(dirname(output), {recursive:true});
  writeFileSync(output, JSON.stringify(report, null, 2) + '\n');
  console.log(JSON.stringify(report));
  if (!args.includes('--collect-only') && !report.gate_pass) process.exitCode = 1;
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) main();
