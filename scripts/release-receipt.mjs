import {readFileSync,writeFileSync,mkdirSync} from 'node:fs';
import {dirname,resolve} from 'node:path';
import {fileURLToPath} from 'node:url';
import {isDeepStrictEqual} from 'node:util';
import {validateReleaseApproval} from './release-approval.mjs';

export function validateBoundApproval(version, revision, receipt) {
  if(!/^\d+\.\d+\.\d+$/.test(version||'') || !/^[a-f0-9]{40}$/.test(revision||'') ||
      receipt?.source_revision!==revision)
    throw new Error('Formal receipt must bind the exact stable version and application source.');
  return validateReleaseApproval(version,receipt);
}

export function validatePublicRelease(release,{version,revision,status,receipt}) {
  if(!['CANDIDATE','RELEASED','RELEASED_WITH_WARNINGS'].includes(status) ||
      release?.version!==version || release.source_revision!==revision || release.release_status!==status ||
      release.formal_release!==(status!=='CANDIDATE')) throw new Error('Public release identity or channel changed.');
  if(status==='CANDIDATE') {
    if(release.acceptance!==null) throw new Error('A candidate must not advertise formal acceptance.');
  } else {
    validateBoundApproval(version,revision,receipt);
    const mode=status==='RELEASED_WITH_WARNINGS'?'owner-approved-release-with-warnings':'verified-release';
    if(receipt.approval!==mode || release.acceptance?.mode!==mode ||
        release.acceptance.accepted_by!==receipt.accepted_by || release.acceptance.accepted_on!==receipt.accepted_on ||
        !isDeepStrictEqual(release.acceptance.waivers,receipt.waivers) ||
        !isDeepStrictEqual(release.acceptance.gates,receipt.gates))
      throw new Error('Public acceptance differs from the approved source-bound receipt.');
  }
  return release;
}

function main() {
  const args=process.argv.slice(2);
  const value=name=>args[args.indexOf(name)+1];
  for(const name of ['--receipt','--version','--revision']) if(!args.includes(name) || !value(name)) throw new Error(`Missing ${name}`);
  const path=resolve(value('--receipt'));const bytes=readFileSync(path);
  if(bytes.length>256*1024) throw new Error('Acceptance receipt exceeds 256 KiB.');
  const receipt=validateBoundApproval(value('--version'),value('--revision'),JSON.parse(bytes.toString('utf8')));
  if(args.includes('--public')) {
    validatePublicRelease(JSON.parse(readFileSync(value('--public'),'utf8')),{version:receipt.version,
      revision:receipt.source_revision,status:value('--release-status'),receipt});
    console.log('Built release metadata matches the approved receipt.');
  } else {
    if(!args.includes('--output') || !value('--output')) throw new Error('Missing --output');
    const output=resolve(value('--output'));mkdirSync(dirname(output),{recursive:true});
    writeFileSync(output,bytes,{flag:'wx'});
    console.log(`Validated formal receipt for ${receipt.version} / ${receipt.source_revision}; original bytes preserved.`);
  }
}
if(process.argv[1] && resolve(process.argv[1])===fileURLToPath(import.meta.url)) main();
