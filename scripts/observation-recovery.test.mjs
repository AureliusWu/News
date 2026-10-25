import test from 'node:test';
import assert from 'node:assert/strict';
import {shouldRecover,isRecoveryRef} from './observation-recovery.mjs';
const now=Date.parse('2026-10-25T12:00:00Z');
const options={version:'1.1.0-alpha.1',revision:'a'.repeat(40),now};
const row=()=>({base_url:'https://aureliuswu.github.io/News/',observed_at:new Date(now).toISOString(),
  release:{version:options.version,source_revision:options.revision},source_health:{same_generation:true},
  snapshot:{collector_gate_pass:true,age_hours:1.5}});
test('recovery accepts only this version tag or its explicit candidate tag',()=>{
  for(const ref of ['v1.1.0','v1.1.0-rc.1','v1.1.0-alpha.2']) assert.equal(isRecoveryRef('1.1.0',ref),true);
  for(const ref of ['main','v1.0.0','v1x1x0-rc.1','v1.1.0-rc.1/other']) assert.equal(isRecoveryRef('1.1.0',ref),false);
});
test('recovery is limited to the currently observed pinned source and version',()=>{
  assert.equal(shouldRecover(row(),options),true);
  for(const change of [value=>value.release.version='1.0.0',value=>value.release.source_revision='b'.repeat(40),
    value=>value.base_url='https://example.org/',value=>value.observed_at='2026-10-24T12:00:00Z',
    value=>value.release=null]) {
    const value=row();change(value);assert.equal(shouldRecover(value,options),false);
  }
});
test('fresh data, active publishing, and hourly cooldown do not trigger duplicate publishing',()=>{
  const fresh=row();fresh.snapshot.age_hours=0.5;
  assert.equal(shouldRecover(fresh,options),false);
  assert.equal(shouldRecover(row(),{...options,publisherBusy:true}),false);
  assert.equal(shouldRecover(row(),{...options,lastAttempt:now-1000}),false);
});
test('observed generation mismatch is recoverable without claiming a passing observation',()=>{
  const broken=row();broken.snapshot.age_hours=0.2;broken.source_health.same_generation=false;
  assert.equal(shouldRecover(broken,options),true);assert.equal(broken.source_health.same_generation,false);
});
