import test from 'node:test';
import assert from 'node:assert/strict';
import {observePublic, summarizeScheduledRuns} from './observe-public.mjs';

const now = new Date('2026-11-20T04:00:00Z');
const hour = 3600000;

function run(id, hoursAgo, event = 'schedule') {
  return {databaseId: id, createdAt: new Date(now.getTime() - hoursAgo * hour).toISOString(), event};
}

test('cadence ignores future, duplicate, manual and out-of-window runs', () => {
  const relevant = [run(1, 4), run(2, 14), run(3, 17)];
  const other = [run(4, -1), run(5, 170), run(6, 1, 'workflow_dispatch'), relevant[0]];
  const summary = summarizeScheduledRuns([...relevant, ...other], now.getTime());
  assert.equal(summary.run_count_7d, 3);
  assert.deepEqual(summary.intervals_hours, [3, 10]);
  assert.equal(summary.max_interval_hours, 10);
  assert.equal(summary.latest_run_id, 1);
  assert.equal(summary.hours_since_last_run, 4);
});

test('cadence covers a complete normal seven days of half-hour runs', () => {
  const runs = Array.from({length: 336}, (_, index) => run(index + 1, (index + 1) / 2));
  const result = summarizeScheduledRuns(runs, now.getTime());
  assert.equal(result.run_count_7d, 336);
  assert.equal(result.max_interval_hours, 0.5);
  assert.equal(result.history_capped, false);
});

test('broken source-health fetch retains the partial public sample and independent cadence', async () => {
  const resources = new Map([
    ['release.json', JSON.stringify({version: '1.1.0', source_revision: 'a'.repeat(40), formal_release: true})],
    ['', '<html lang="zh-CN"><script src="assets/index.js"></script></html>'],
    ['data/news.json', JSON.stringify({generated_at: '2026-11-20T01:00:00Z', health: {gate_pass: true}})]
  ]);
  const observation = await observePublic(now, {
    get: async path => {
      if (!resources.has(path)) throw new Error('HTTP 503 from source-health');
      return {status: 200, body: resources.get(path)};
    },
    listRuns: since => {
      assert.equal(since, '2026-11-13T04:00:00.000Z');
      return [run(1, 7), run(2, 18)];
    }
  });
  assert.equal(observation.release.version, '1.1.0');
  assert.equal(observation.snapshot.age_hours, 3);
  assert.equal(observation.snapshot.freshness_2h_pass, false);
  assert.match(observation.transport_error, /HTTP 503/);
  assert.equal(observation.scheduling.max_interval_hours, 11);
  assert.equal(observation.source_health, undefined);
});

test('schedule lookup failure stays separate from public transport failure', async () => {
  const observation = await observePublic(now, {
    get: async () => { throw new Error('HTTP 503 from Pages'); },
    listRuns: () => { throw new Error('Actions history unavailable'); }
  });
  assert.equal(observation.transport_error, 'HTTP 503 from Pages');
  assert.equal(observation.scheduling.error, 'Actions history unavailable');
});
