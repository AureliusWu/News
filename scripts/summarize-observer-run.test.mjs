import test from 'node:test';
import assert from 'node:assert/strict';
import {execFileSync} from 'node:child_process';
import {mkdtempSync, readFileSync, rmdirSync, unlinkSync, writeFileSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {fileURLToPath} from 'node:url';
import {classifyPublicSample, formatObserverSummary} from './summarize-observer-run.mjs';

const pinned = {version: '1.1.0', revision: 'a'.repeat(40)};

function sample(ageHours, fresh) {
  return {
    schema_version: 1,
    base_url: 'https://aureliuswu.github.io/News/',
    html: {status: 200, language_zh_cn: true},
    release: {version: pinned.version, source_revision: pinned.revision},
    snapshot: {status: 200, schema_version: 1, collector_gate_pass: true,
      age_hours: ageHours, freshness_2h_pass: fresh},
    source_health: {same_generation: true},
    scheduling: {hours_since_last_run: 2.80, max_interval_hours: 10.13}
  };
}

test('single bound sample reports stale separately from a fresh sample at the existing boundary', () => {
  assert.equal(classifyPublicSample(sample(2, true), pinned).status, 'FRESH');
  assert.equal(classifyPublicSample(sample(2.001, false), pinned).status, 'STALE');
});

test('failed fetch and wrong pinned revision cannot be reported as stale or fresh', () => {
  const row = sample(2.8, false);
  assert.equal(classifyPublicSample(null, pinned).status, 'UNAVAILABLE');
  assert.equal(classifyPublicSample({...row, transport_error: 'timeout'}, pinned).status, 'UNAVAILABLE');
  assert.equal(classifyPublicSample(row, {...pinned, revision: 'b'.repeat(40)}).status, 'UNBOUND');
});

test('invalid future timestamp and unpaired source health remain visible as invalid observations', () => {
  assert.equal(classifyPublicSample(sample(-0.1, false), pinned).status, 'INVALID');
  const row = sample(2.8, false);
  row.source_health.same_generation = false;
  assert.equal(classifyPublicSample(row, pinned).status, 'INVALID');
});

test('cadence summary marks capped input and remains separate from release acceptance', () => {
  const row = sample(2.8, false);
  row.scheduling.history_capped = true;
  const summary = formatObserverSummary(row, classifyPublicSample(row, pinned));
  assert.match(summary, /Snapshot age: 2\.80 h/);
  assert.match(summary, /Longest observed gap.*10\.13 h/);
  assert.match(summary, /older runs may be absent/);
  assert.match(summary, /separate from seven-day coverage and formal release acceptance/);
});

test('workflow entry point uses the latest raw sample and emits a nonfatal stale annotation', () => {
  const dir = mkdtempSync(join(tmpdir(), 'news-observer-summary-'));
  const rawPaths = [
    join(dir, '2026-11-20T00-30-00.000Z.json'),
    join(dir, '2026-11-20T03-42-52.809Z.json'),
    join(dir, 'recovery-1795146172809.json')
  ];
  const summaryPath = join(dir, 'summary.md');
  try {
    writeFileSync(rawPaths[0], JSON.stringify(sample(0.3, true)));
    writeFileSync(rawPaths[1], JSON.stringify(sample(2.8, false)));
    writeFileSync(rawPaths[2], '{"dispatched":false}');
    const output = execFileSync(process.execPath, [
      fileURLToPath(new URL('./summarize-observer-run.mjs', import.meta.url)), dir
    ], {encoding: 'utf8', env: {...process.env,
      OBSERVER_VERSION: pinned.version, OBSERVER_REVISION: pinned.revision, GITHUB_STEP_SUMMARY: summaryPath}});
    assert.match(output, /::warning title=News public snapshot STALE::/);
    assert.match(readFileSync(summaryPath, 'utf8'), /\*\*STALE\*\*/);
  } finally {
    for (const path of [...rawPaths, summaryPath]) {
      try { unlinkSync(path); } catch (error) { if (error.code !== 'ENOENT') throw error; }
    }
    rmdirSync(dir);
  }
});
