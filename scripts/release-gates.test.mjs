import test from 'node:test';
import assert from 'node:assert/strict';
import {readAiPolicy, validateAiPolicy} from './ai-feature-policy.mjs';
import {evaluateFreshness, compactObservation} from './freshness-gate.mjs';
import {isSnapshotPair} from './snapshot-pair.mjs';

const now = Date.parse('2026-10-08T16:00:00Z');
const slot = 1800000;
function observation(time) {
  return {schema_version:1, observed_at:new Date(time).toISOString(), base_url:'https://aureliuswu.github.io/News/',
    html:{status:200,language_zh_cn:true}, snapshot:{status:200,generated_at:new Date(time-60000).toISOString(),collector_gate_pass:true},
    source_health:{same_generation:true}, release:{version:'0.9.0-alpha.1',source_revision:'synthetic-test'}};
}
function week() {return Array.from({length:337},(_,i)=>observation(now - 336*slot + i*slot));}
const options = {now,expectedVersion:'0.9.0-alpha.1'};

test('content AI is disabled and has zero budgets',()=>{
  const policy=readAiPolicy(); assert.equal(policy.enabled,false); assert.equal(policy.max_cost_usd,0);
  assert.equal(policy.max_requests_per_day,0); assert.equal(policy.max_cache_entries,0);
});
test('enabled features, cost, credentials, missing guards cannot pass policy',()=>{
  const policy=readAiPolicy();
  for(const change of [{enabled:true},{max_cost_usd:1},{translation_enabled:true},{api_key:'synthetic'},
    {source_citations_required:false},{summary_enabled:true},{original_switch_required:false}])
    assert.throws(()=>validateAiPolicy({...policy,...change}));
});
test('complete synthetic week passes only the predicate, not production acceptance',()=>{
  const report=evaluateFreshness(week(),options); assert.equal(report.gate_pass,true);
  assert.equal(report.expected_slots,336); assert.equal(report.passing_slots,336); assert.equal(report.formal_release,false);
});
test('one sample and duplicate samples cannot manufacture seven days',()=>{
  const report=evaluateFreshness(Array(500).fill(observation(now-slot)),options);
  assert.equal(report.gate_pass,false); assert.equal(report.observed_slots,1); assert.equal(report.status,'WARMING_UP');
});
test('missing slots count as failed coverage',()=>{
  const rows=week().filter((_,i)=>i===0 || i>20);
  const report=evaluateFreshness(rows,options); assert.equal(report.gate_pass,false); assert.equal(report.missing_slots,20);
});
test('stale and contradictory retry cannot be hidden',()=>{
  const rows=week(); const bad=structuredClone(rows[100]);
  bad.observed_at=new Date(Date.parse(bad.observed_at)+1000).toISOString();
  bad.snapshot.generated_at=new Date(Date.parse(bad.observed_at)-3*3600000).toISOString(); rows.push(bad);
  const report=evaluateFreshness(rows,options); assert.equal(report.failed_slots,1); assert.equal(report.passing_slots,335);
});
test('future generation, report mismatch, failed transport reduce valid observations',()=>{
  for(const change of [r=>r.snapshot.generated_at=new Date(Date.parse(r.observed_at)+600000).toISOString(),
    r=>r.source_health.same_generation=false,r=>r.transport_error='synthetic',r=>r.snapshot.collector_gate_pass=false]) {
    const rows=week(); change(rows[2]); assert.equal(evaluateFreshness(rows,options).failed_slots,1);
  }
});
test('another deployed version does not qualify the candidate',()=>{
  const rows=week(); for(const row of rows) row.release.version='0.2.0';
  assert.equal(evaluateFreshness(rows,options).gate_pass,false);
  assert.equal(evaluateFreshness(rows,options).observed_slots,0);
});
test('compaction retains timestamps and failures, not action success statistics',()=>{
  const row=observation(now); row.workflow_history=[{conclusion:'success'}]; row.transport_error='synthetic';
  const compact=compactObservation(row); assert.equal(compact.observed_at,row.observed_at);
  assert.equal(compact.transport_error,'synthetic'); assert.equal(compact.workflow_history,undefined);
});

const currentNews = {generated_at:'2026-10-03T00:00:00Z',snapshot_id:'synthetic-current-id',content_sha256:'snapshot-only'};
const currentHealth = {checked_at:currentNews.generated_at,snapshot_id:currentNews.snapshot_id};
test('current reports bind by snapshot_id and checked_at without snapshot-only fields',()=>{
  assert.equal(isSnapshotPair(currentNews,currentHealth),true);
});
test('legacy reports retain the timestamp binding',()=>{
  assert.equal(isSnapshotPair({generated_at:currentNews.generated_at},{checked_at:currentNews.generated_at}),true);
});
test('equal IDs cannot hide a different check timestamp',()=>{
  assert.equal(isSnapshotPair(currentNews,{...currentHealth,checked_at:'2026-10-02T00:00:00Z'}),false);
});
test('equal timestamps cannot hide a missing or wrong current ID',()=>{
  for (const snapshot_id of [undefined,null,'','wrong'])
    assert.equal(isSnapshotPair(currentNews,{...currentHealth,snapshot_id}),false);
});
test('current reports without checked_at fail closed',()=>{
  assert.equal(isSnapshotPair(currentNews,{snapshot_id:currentNews.snapshot_id,generated_at:currentNews.generated_at}),false);
});
test('invalid dates, IDs and non-object inputs fail closed',()=>{
  for (const snapshot_id of ['',0,{},[]])
    assert.equal(isSnapshotPair({...currentNews,snapshot_id},{...currentHealth,snapshot_id}),false);
  assert.equal(isSnapshotPair({generated_at:'invalid'},{checked_at:'invalid'}),false);
  for (const value of [null,undefined,[],1]) {
    assert.equal(isSnapshotPair(value,currentHealth),false);
    assert.equal(isSnapshotPair(currentNews,value),false);
  }
});
test('a current report cannot be paired with an unidentified legacy snapshot',()=>{
  assert.equal(isSnapshotPair({generated_at:currentNews.generated_at},currentHealth),false);
});
test('correction never erases a historic failed sample or contradictory retry',()=>{
  const rows=week(); const bad=structuredClone(rows[10]); bad.source_health.same_generation=false;
  rows.push(bad);
  const report=evaluateFreshness(rows,options);
  assert.equal(report.failed_slots,1);
  assert.equal(compactObservation(bad).source_health.same_generation,false);
});
