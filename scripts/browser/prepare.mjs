import {execFileSync} from 'node:child_process';
import {createHash} from 'node:crypto';
import {copyFile, mkdir, readFile, writeFile} from 'node:fs/promises';
import {join, resolve} from 'node:path';
import {output, requireIsolatedCI} from './server.mjs';

requireIsolatedCI();
const sha = bytes => createHash('sha256').update(bytes).digest('hex');
const origin = 'https://aureliuswu.github.io/News/data/';
await mkdir(join(output, 'frozen'), {recursive: true});

async function download(name) {
  const url = new URL(name, origin);
  if (url.origin !== new URL(origin).origin || !url.pathname.startsWith('/News/data/')) {
    throw new Error('Frozen input escaped the public data directory.');
  }
  const response = await fetch(url, {signal: AbortSignal.timeout(30000), cache: 'no-store'});
  if (!response.ok) throw new Error(`${url} returned ${response.status}`);
  const bytes = Buffer.from(await response.arrayBuffer());
  if (bytes.length > 4 * 1024 * 1024) throw new Error('Frozen input exceeds 4 MiB.');
  // Preserve received public bytes even when a later contract check fails.
  await writeFile(join(output, 'frozen', name), bytes);
  return {url: url.href, bytes, json: JSON.parse(bytes.toString('utf8'))};
}

const news = await download('news.json');
if (!/^[a-f0-9]{24}$/.test(news.json.snapshot_id) || !news.json.health?.gate_pass ||
    !Array.isArray(news.json.articles) || !news.json.articles.length) throw new Error('Invalid live news input.');
const files = new Map([['news.json', news]]);
for (const [field, prefix] of [['events_file', 'events'], ['source_health_file', 'source-health']]) {
  const name = `${prefix}.${news.json.snapshot_id}.json`;
  if (news.json[field] !== name) throw new Error(`Unexpected bound asset ${field}.`);
  const asset = await download(name);
  const binding = prefix === 'events'
    ? [['snapshot_id', 'snapshot_id'], ['generated_at', 'generated_at'], ['content_sha256', 'content_sha256']]
    : [['snapshot_id', 'snapshot_id'], ['checked_at', 'generated_at']];
  for (const [assetKey, newsKey] of binding) {
    if (asset.json[assetKey] !== news.json[newsKey]) {
      throw new Error(`Mismatched frozen asset ${name}: ${assetKey}`);
    }
  }
  if (prefix === 'source-health') {
    for (const [key, value] of Object.entries(news.json.health)) {
      if (JSON.stringify(asset.json.summary?.[key]) !== JSON.stringify(value)) {
        throw new Error(`Mismatched frozen health summary ${name}: ${key}`);
      }
    }
    const checks = Object.values(asset.json.checks || {});
    if (!checks.length || checks.some(value => value !== true)) {
      throw new Error(`Frozen source-health checks did not pass: ${name}`);
    }
  }
  files.set(name, asset);
  if (prefix === 'source-health') files.set('source-health.json', asset);
}
const inputs = [];
for (const [name, asset] of files) {
  await writeFile(join(output, 'frozen', name), asset.bytes);
  inputs.push({name, url: asset.url, bytes: asset.bytes.length, sha256: sha(asset.bytes)});
}

const variants = {};
for (const name of ['baseline', 'candidate']) {
  const root = resolve(process.env[`${name.toUpperCase()}_ROOT`] || `verification-inputs/${name}`);
  const revision = execFileSync('git', ['rev-parse', 'HEAD'], {cwd: root, encoding: 'utf8'}).trim();
  const dist = join(output, 'builds', name);
  execFileSync('npm', ['run', 'build', '--', '--outDir', dist], {
    cwd: join(root, 'frontend'), stdio: 'inherit',
    env: {...process.env, BASE_PATH: '/News/', VITE_NEWS_MODE: 'snapshot', VITE_API_BASE_URL: ''},
  });
  await mkdir(join(dist, 'data'), {recursive: true});
  for (const [file] of files) {
    await copyFile(join(output, 'frozen', file), join(dist, 'data', file));
    if (sha(await readFile(join(dist, 'data', file))) !== inputs.find(input => input.name === file).sha256) {
      throw new Error(`Frozen bytes changed in ${name}/${file}.`);
    }
  }
  if (name === 'candidate') {
    // Candidate wire optimization uses exactly the frozen baseline articles and metadata.
    const lookup = new Map(news.json.sources.map((source, index) => [source.slug, index]));
    const compact = {wire_schema_version: 1, snapshot: {...news.json, articles: news.json.articles.map(article => {
      const {source, ...fields} = article;
      const source_index = lookup.get(source.slug);
      if (JSON.stringify(source) !== JSON.stringify(news.json.sources[source_index])) throw new Error('Compact input source mismatch.');
      return {...fields, source_index};
    })}};
    await writeFile(join(dist, 'data', 'news.compact.json'), JSON.stringify(compact));
    const preview = {...compact,view:'home-preview-v1',total_articles:news.json.articles.length,
      snapshot:{...compact.snapshot,articles:compact.snapshot.articles.slice(0,30)}};
    await writeFile(join(dist,'data','news.home.json'),JSON.stringify(preview));
  }
  const html = await readFile(join(dist, 'index.html'), 'utf8');
  const entry = html.match(/<script\b[^>]*type="module"[^>]*src="([^"]+)"/)?.[1];
  if (!entry?.startsWith('/News/assets/')) throw new Error(`Missing built entry for ${name}.`);
  variants[name] = {
    root, dist, revision, entry, html_sha256: sha(html),
    entry_sha256: sha(await readFile(join(dist, entry.slice('/News/'.length)))),
    sw_sha256: sha(await readFile(join(dist, 'sw.js'))),
  };
}
if (variants.baseline.entry === variants.candidate.entry) throw new Error('Comparison entries must differ.');
await writeFile(join(output, 'manifest.json'), JSON.stringify({
  schema_version: 1, captured_at: new Date().toISOString(),
  snapshot_id: news.json.snapshot_id, generated_at: news.json.generated_at,
  content_sha256: news.json.content_sha256, article_count: news.json.articles.length,
  inputs, ...variants,
  scope: 'Isolated CI; exact frozen public JSON; no production deployment, phone or Windows gate closure.',
}, null, 2) + '\n');
