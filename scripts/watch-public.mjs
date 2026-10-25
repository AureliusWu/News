import {spawnSync, execFileSync} from 'node:child_process';
import {mkdirSync, readFileSync, writeFileSync} from 'node:fs';
import {resolve, sep} from 'node:path';
import {setTimeout as delay} from 'node:timers/promises';
import {mergeObservations, evaluateFreshness} from './freshness-gate.mjs';
import {shouldRecover,isRecoveryRef,publisherBlocksRecovery} from './observation-recovery.mjs';

const directory=resolve(process.env.NEWS_OBSERVER_OUTPUT || 'artifacts/v1-cloud-observer');
if(!directory.startsWith(resolve('artifacts')+sep)) throw new Error('Observer output must remain inside workspace artifacts.');
const incoming=resolve(directory,'incoming');
const continuous=process.env.NEWS_OBSERVER_CONTINUOUS==='true';
const canRecover=process.env.NEWS_AUTO_RECOVERY_ENABLED==='true';
const expectedVersion=process.env.OBSERVER_VERSION;
const expectedRevision=process.env.OBSERVER_REVISION;
const recoveryRef=process.env.NEWS_RECOVERY_REF || '';
if (!expectedVersion || !/^[a-f0-9]{40}$/.test(expectedRevision || '')) throw new Error('Observer requires a pinned version and full application SHA.');
if ((continuous || canRecover) && (process.platform!=='linux' || process.env.GITHUB_ACTIONS!=='true'
    || process.env.GITHUB_REPOSITORY!=='AureliusWu/News')) throw new Error('Continuous monitoring and bounded recovery run only in this repository Actions job.');
if (canRecover && !isRecoveryRef(expectedVersion,recoveryRef))
  throw new Error('Recovery requires the observed version or its explicit candidate tag, never an arbitrary branch.');
const historyPath=resolve(directory,'history.json');
const bytes=readFileSync(historyPath);
const history=JSON.parse(bytes);
if(bytes.length>512*1024 || history.schema_version!==1 || !Array.isArray(history.observations)) throw new Error('Invalid prior observation history; do not reset it.');
let rows=history.observations;
let lastAttempt=0;
mkdirSync(incoming,{recursive:true});
const api=path=>JSON.parse(execFileSync('gh',['api',`repos/AureliusWu/News/${path}`],{encoding:'utf8',timeout:30000}));
const startedAt=Date.now();
for(let sample=0;sample<(continuous?11:1);sample++) {
  if(sample) await delay(Math.max(1,startedAt+sample*30*60000-Date.now()));
  const child=spawnSync(process.execPath,['scripts/observe-public.mjs',incoming],{encoding:'utf8',timeout:150000,maxBuffer:1024*1024});
  let row;
  try {
    const receipt=JSON.parse(child.stdout);
    const path=resolve(receipt.path);
    if(!path.startsWith(incoming+sep)) throw new Error('Observation path escaped its directory.');
    const raw=readFileSync(path);if(raw.length>256*1024) throw new Error('Raw observation too large.');
    row=JSON.parse(raw);
  } catch(error) {
    row={schema_version:1,observed_at:new Date().toISOString(),base_url:'https://aureliuswu.github.io/News/',
      transport_error:`Observation process failed: ${String(child.error || error).slice(0,300)}`};
    writeFileSync(resolve(incoming,row.observed_at.replaceAll(':','-')+'.json'),JSON.stringify(row,null,2)+'\n');
  }
  const now=Date.now();
  rows=mergeObservations([...rows,row],now);
  const rawHistory=JSON.stringify({schema_version:1,observations:rows});
  if(Buffer.byteLength(rawHistory)>512*1024) throw new Error('Observation history exceeds 512 KiB.');
  writeFileSync(historyPath,rawHistory+'\n');
  const report=evaluateFreshness(rows,{now,expectedVersion,expectedRevision});
  writeFileSync(resolve(directory,'report.json'),JSON.stringify(report,null,2)+'\n');
  console.log(JSON.stringify({sample:sample+1,observed_at:row.observed_at,transport_error:row.transport_error,
    age_hours:row.snapshot?.age_hours,passing_slots:report.passing_slots,missing_slots:report.missing_slots,status:report.status}));
  if(canRecover && shouldRecover(row,{version:expectedVersion,revision:expectedRevision,now,lastAttempt})) {
    const recovery={attempted_at:new Date().toISOString(),ref:recoveryRef,source_revision:expectedRevision,dispatched:false};
    try {
      const tag=api(`git/ref/tags/${recoveryRef}`);
      if(tag.object?.type!=='commit' || tag.object.sha!==expectedRevision) throw new Error('Recovery tag is not the pinned application source.');
      const runs=api('actions/workflows/deploy-gh-pages.yml/runs?per_page=10').workflow_runs;
      if(!publisherBlocksRecovery(runs,{revision:expectedRevision,ref:recoveryRef,now})) {
        lastAttempt=now;
        execFileSync('gh',['workflow','run','deploy-gh-pages.yml','--repo','AureliusWu/News','--ref','main','-f',`source_ref=${recoveryRef}`,'-f','publish=true','-f','data_only=true'],{encoding:'utf8',timeout:30000});
        recovery.dispatched=true;
      } else recovery.skipped='Publisher active or a pinned manual attempt is less than one hour old.';
    } catch(error) { recovery.error=String(error.message).slice(0,500); lastAttempt=now; }
    writeFileSync(resolve(incoming,`recovery-${Date.now()}.json`),JSON.stringify(recovery,null,2)+'\n');
    console.log(JSON.stringify(recovery));
  }
}
