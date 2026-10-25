import test from 'node:test';
import assert from 'node:assert/strict';
import {validateReleaseApproval} from './release-approval.mjs';

function approval() {
  return {schema_version: 1, version: '1.0.0', approval: 'owner-approved-release-with-warnings',
    accepted_by: 'repository-owner', accepted_on: '2026-10-15', authorization_source: 'synthetic test fixture',
    waivers: [{id: 'synthetic-open-gate', disposition: 'WAIVED_FOR_THIS_RELEASE', observed_status: 'FAIL',
      limitation: 'Synthetic failed gate, not a production receipt.', evidence: ['synthetic evidence']}]};
}

test('verified release requires complete version/source-bound passing gates', () => {
  const source_revision = 'a'.repeat(40);
  const value = {schema_version:1,version:'1.1.0',approval:'verified-release',source_revision,waivers:[],
    gates:['regression','source_integrity','performance','freshness','upgrade','devices','rollback','public_smoke'].map(id=>
      ({id,status:'PASS',source_revision,version:'1.1.0',evidence:['synthetic test receipt']}))};
  assert.equal(validateReleaseApproval('1.1.0',value),value);
  for (const change of [v=>v.gates.pop(),v=>v.gates[0].status='FAIL',v=>v.gates[0].source_revision='b'.repeat(40),
    v=>v.gates[0].version='1.0.0',v=>v.gates[0].evidence=[],v=>v.waivers.push({id:'open'})]) {
    const bad=structuredClone(value); change(bad); assert.throws(()=>validateReleaseApproval('1.1.0',bad));
  }
});
test('prerelease versions remain candidates without a formal approval', () => {
  assert.equal(validateReleaseApproval('0.9.0-alpha.1'), null);
});
test('stable releases fail closed without explicit approval', () => {
  for (const value of [undefined, null, {}, {...approval(), approval: 'automatic'}]) {
    assert.throws(() => validateReleaseApproval('1.0.0', value));
  }
});
test('approval for one version cannot authorize another release', () => {
  assert.throws(() => validateReleaseApproval('1.0.1', approval()));
});
test('waived failures retain their actual status', () => {
  const value = approval();
  assert.equal(validateReleaseApproval('1.0.0', value), value);
  assert.equal(value.waivers[0].observed_status, 'FAIL');
});
test('empty, duplicate, or passing waivers are rejected', () => {
  const empty = approval(); empty.waivers = [];
  const duplicate = approval(); duplicate.waivers.push({...duplicate.waivers[0]});
  const passing = approval(); passing.waivers[0].observed_status = 'PASS';
  for (const value of [empty, duplicate, passing]) assert.throws(() => validateReleaseApproval('1.0.0', value));
});
test('missing owner, limitation or evidence is rejected', () => {
  for (const change of [value => {value.accepted_by = 'automation';},
    value => {value.waivers[0].limitation = '';}, value => {value.waivers[0].evidence = [];}]) {
    const value = approval(); change(value);
    assert.throws(() => validateReleaseApproval('1.0.0', value));
  }
});
