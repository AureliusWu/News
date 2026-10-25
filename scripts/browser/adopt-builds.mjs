import {createHash} from 'node:crypto';
import {execFileSync} from 'node:child_process';
import {readFile,writeFile} from 'node:fs/promises';
import {join,resolve} from 'node:path';
import {manifest,output,requireIsolatedCI} from './server.mjs';

requireIsolatedCI();
if(process.platform!=='win32') throw new Error('Only the Windows Edge job adopts the Linux-built pair.');
const data=await manifest();
await writeFile(join(output,'manifest.linux.json'),JSON.stringify(data,null,2)+'\n',{flag:'wx'});
const hash=bytes=>createHash('sha256').update(bytes).digest('hex');
for(const name of ['baseline','candidate']) {
  const variant=data[name];
  const root=resolve(process.env[`${name.toUpperCase()}_ROOT`]);
  const revision=execFileSync('git',['rev-parse','HEAD'],{cwd:root,encoding:'utf8'}).trim();
  if(revision!==variant.revision || !/^\/News\/assets\/[\w.-]+\.js$/.test(variant.entry))
    throw new Error(`Unexpected application identity for ${name}.`);
  const dist=join(output,'builds',name);
  for(const [file,expected] of [['index.html',variant.html_sha256],['sw.js',variant.sw_sha256],
    [variant.entry.slice('/News/'.length),variant.entry_sha256]]) {
    if(hash(await readFile(join(dist,file)))!==expected) throw new Error(`Changed built bytes: ${name}/${file}`);
  }
  for(const input of data.inputs) {
    if(!/^[\w.-]+\.json$/.test(input.name) ||
        hash(await readFile(join(dist,'data',input.name)))!==input.sha256)
      throw new Error(`Changed frozen input: ${name}/${input.name}`);
  }
  variant.root=root; variant.dist=dist;
}
data.scope='Windows GitHub Actions Edge; identical frozen input and Linux-built application pair. No local Windows backend lifecycle or physical phone verification.';
await writeFile(join(output,'manifest.json'),JSON.stringify(data,null,2)+'\n');
