import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtempSync,writeFileSync,readFileSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import {validateBoundApproval,validatePublicRelease} from './release-receipt.mjs';
const revision='a'.repeat(40),version='1.1.0';
const receipt=()=>({schema_version:1,version,source_revision:revision,approval:'owner-approved-release-with-warnings',
  accepted_by:'repository-owner',accepted_on:'2026-10-26',authorization_source:'Synthetic explicit approval fixture, not production evidence.',
  waivers:[{id:'synthetic-open-gate',disposition:'WAIVED_FOR_THIS_RELEASE',observed_status:'NOT_RUN',
    limitation:'Synthetic uncompleted gate; not passed.',evidence:['synthetic test evidence']}]});
const metadata=r=>({version:r.version,source_revision:r.source_revision,formal_release:true,release_status:'RELEASED_WITH_WARNINGS',
  acceptance:{mode:r.approval,accepted_by:r.accepted_by,accepted_on:r.accepted_on,waivers:r.waivers}});
test('owner waiver stays source-bound and retains its original nonpassing status',()=>{
  const r=receipt(),original=structuredClone(r);assert.equal(validateBoundApproval(version,revision,r),r);assert.deepEqual(r,original);
});
test('an approval for another source, version or prerelease cannot promote this application',()=>{
  for(const [v,s,r] of [['1.0.0',revision,receipt()],[version,'b'.repeat(40),receipt()],['1.1.0-rc.1',revision,receipt()],
    [version,revision,{...receipt(),source_revision:undefined}]]) assert.throws(()=>validateBoundApproval(v,s,r));
});
test('missing consent and waivers rewritten as PASS cannot be bound for publication',()=>{
  const missing=receipt();delete missing.authorization_source;
  const passing=receipt();passing.waivers[0].observed_status='PASS';
  for(const r of [missing,passing]) assert.throws(()=>validateBoundApproval(version,revision,r));
});
test('public warned release must preserve the complete approved waiver details',()=>{
  const r=receipt(),options={version,revision,status:'RELEASED_WITH_WARNINGS',receipt:r};
  assert.equal(validatePublicRelease(metadata(r),options).formal_release,true);
  for(const change of [v=>v.source_revision='b'.repeat(40),v=>v.formal_release=false,v=>v.release_status='CANDIDATE',
    v=>v.acceptance.waivers=[],v=>v.acceptance.waivers[0].limitation='changed',v=>v.acceptance.accepted_on='2026-10-25']) {
    const value=structuredClone(metadata(r));change(value);assert.throws(()=>validatePublicRelease(value,options));
  }
});
test('candidate and normal-release claims cannot reuse a warned approval',()=>{
  const candidate={version,source_revision:revision,formal_release:false,release_status:'CANDIDATE',acceptance:null};
  assert.equal(validatePublicRelease(candidate,{version,revision,status:'CANDIDATE'}),candidate);
  assert.throws(()=>validatePublicRelease({...candidate,formal_release:true},{version,revision,status:'CANDIDATE'}));
  assert.throws(()=>validatePublicRelease({...metadata(receipt()),release_status:'RELEASED'},
    {version,revision,status:'RELEASED',receipt:receipt()}));
});
test('CLI preserves approved JSON bytes and refuses a different build source',()=>{
  const directory=mkdtempSync(join(tmpdir(),'news-receipt-')),input=join(directory,'owner.json'),output=join(directory,'bound.json');
  const bytes=JSON.stringify(receipt(),null,2)+'\n';writeFileSync(input,bytes);
  const args=[fileURLToPath(new URL('./release-receipt.mjs',import.meta.url)),'--receipt',input,'--version',version,'--revision',revision,'--output',output];
  assert.equal(spawnSync(process.execPath,args,{encoding:'utf8'}).status,0);assert.equal(readFileSync(output,'utf8'),bytes);
  const other=[...args];other[other.indexOf('--revision')+1]='b'.repeat(40);
  assert.notEqual(spawnSync(process.execPath,other,{encoding:'utf8'}).status,0);
});
