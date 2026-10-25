import {execFileSync} from 'node:child_process';
import {existsSync, mkdirSync} from 'node:fs';
import {resolve} from 'node:path';
const repo = 'AureliusWu/News';
const directory = resolve('artifacts/v1-cloud-observer');
mkdirSync(directory, {recursive:true});
const api = path => JSON.parse(execFileSync('gh',['api',`repos/${repo}/${path}`],{encoding:'utf8',timeout:30000}));
const runs = api('actions/workflows/observe-news.yml/runs?status=completed&branch=main&per_page=20').workflow_runs;
let restored = false;
for (const run of runs) {
  if (String(run.id) === process.env.GITHUB_RUN_ID) continue;
  const artifacts = api(`actions/runs/${run.id}/artifacts`).artifacts;
  if (!artifacts.some(item => item.name === 'news-independent-observations' && !item.expired)) continue;
  execFileSync('gh',['run','download',String(run.id),'--repo',repo,'--name','news-independent-observations','--dir',directory],{stdio:'inherit',timeout:60000});
  if (!existsSync(resolve(directory,'history.json'))) throw new Error('Existing history artifact is incomplete; do not reset history.');
  console.log(JSON.stringify({restored_from:run.id,conclusion:run.conclusion})); restored = true; break;
}
if (!restored) throw new Error('No retained observer history available. Preserve incoming raw evidence; explicit recovery is required.');
