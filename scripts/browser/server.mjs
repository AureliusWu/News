import {spawn} from 'node:child_process';
import {once} from 'node:events';
import {appendFile, readFile} from 'node:fs/promises';
import {join, resolve} from 'node:path';

// These process/network tests belong to an isolated runner, not the user's PC.
export function requireIsolatedCI() {
  if (process.env.GITHUB_ACTIONS !== 'true' || process.platform !== 'linux') {
    throw new Error('This harness runs only on isolated Linux GitHub Actions runners.');
  }
}

export const output = resolve(process.env.VERIFICATION_OUTPUT || 'artifacts/ci-browser-verification');
export const siteURL = 'http://127.0.0.1:4177/News/';
export const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
export const manifest = async () => JSON.parse(await readFile(join(output, 'manifest.json'), 'utf8'));

export async function startSite(variant, label) {
  requireIsolatedCI();
  const child = spawn(process.execPath, [
    join(variant.root, 'frontend/node_modules/vite/bin/vite.js'), 'preview',
    '--host', '127.0.0.1', '--port', '4177', '--strictPort',
    '--base', '/News/', '--outDir', variant.dist,
  ], {cwd: join(variant.root, 'frontend'), stdio: ['ignore', 'pipe', 'pipe']});
  let logs = '';
  let spawnError;
  child.stdout.on('data', chunk => { logs += chunk; });
  child.stderr.on('data', chunk => { logs += chunk; });
  child.on('error', error => { spawnError = error; });
  let stopped = false;
  const stop = async () => {
    if (stopped) return;
    stopped = true;
    if (child.exitCode === null && child.signalCode === null && child.pid) {
      const exited = once(child, 'exit');
      child.kill('SIGTERM');
      await Promise.race([exited, sleep(5000)]);
      if (child.exitCode === null && child.signalCode === null) {
        child.kill('SIGKILL');
        await exited;
      }
    }
    await appendFile(join(output, 'preview.log'), `\n--- ${label} ${variant.revision} ---\n${logs}`);
  };
  try {
    for (let attempt = 0; attempt < 80; attempt++) {
      if (spawnError) throw spawnError;
      if (child.exitCode !== null) throw new Error(`Preview exited ${child.exitCode}: ${logs}`);
      try {
        const response = await fetch(siteURL, {signal: AbortSignal.timeout(1000)});
        if (response.ok && (await response.text()).includes(variant.entry)) return {stop};
      } catch { /* Only the child owned by this fixture is being awaited. */ }
      await sleep(250);
    }
    throw new Error(`Preview not ready: ${logs}`);
  } catch (error) {
    await stop();
    throw error;
  }
}
