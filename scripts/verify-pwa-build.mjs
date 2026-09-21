import assert from 'node:assert/strict';
import {existsSync, readFileSync} from 'node:fs';
import {resolve} from 'node:path';
import {runInNewContext} from 'node:vm';

const directory = resolve(process.argv[2] || 'frontend/dist');
const base = process.argv[3] || '/';
assert(base.startsWith('/') && base.endsWith('/') && !base.startsWith('//'), 'Expected an absolute base path ending in /');
const site = new URL(base, 'https://pwa-build.invalid');
const manifestUrl = new URL('manifest.webmanifest', site);
const workerUrl = new URL('sw.js', site);
const manifest = JSON.parse(readFileSync(resolve(directory, 'manifest.webmanifest'), 'utf8'));
assert.equal(manifest.lang, 'zh-CN', 'Manifest language');
assert.equal(new URL(manifest.start_url, manifestUrl).href, site.href, 'Installed app start URL');
assert.equal(new URL(manifest.scope, manifestUrl).href, site.href, 'Installed app scope');
assert(manifest.icons.length >= 2, 'Expected application icons');
for (const icon of manifest.icons) {
  const url = new URL(icon.src, manifestUrl);
  assert.equal(url.origin, site.origin, 'Icon origin');
  assert(url.pathname.startsWith(base), 'Icon must stay inside the deployed base');
  assert(existsSync(resolve(directory, decodeURIComponent(url.pathname.slice(base.length)))), 'Icon artifact must exist');
}

const registration = readFileSync(resolve(directory, 'registerSW.js'), 'utf8');
const registrationMatch = registration.match(/\.register\((['"])([^'"]+)\1,\s*\{\s*scope:\s*(['"])([^'"]+)\3\s*\}\s*\)/);
assert(registrationMatch, 'Expected explicit service worker registration and scope');
assert.equal(new URL(registrationMatch[2], site).href, workerUrl.href, 'Service worker registration URL');
assert.equal(new URL(registrationMatch[4], site).href, site.href, 'Service worker registration scope');

// Inspect generated registration using a non-networking Workbox stub. This checks
// path consistency, not a browser's installation, activation, or offline lifecycle.
const precached = new Set();
const fallbacks = [];
class StrategyStub {}
const workbox = {
  clientsClaim() {}, cleanupOutdatedCaches() {}, registerRoute() {},
  NavigationRoute: StrategyStub, NetworkFirst: StrategyStub, CacheFirst: StrategyStub,
  CacheableResponsePlugin: StrategyStub, ExpirationPlugin: StrategyStub,
  precacheAndRoute(entries) {
    for (const entry of entries) precached.add(new URL(typeof entry === 'string' ? entry : entry.url, workerUrl).href);
  },
  createHandlerBoundToURL(value) {
    const url = new URL(value, workerUrl).href;
    assert(precached.has(url), `Navigation fallback is not precached: ${url}`);
    fallbacks.push(url);
    return () => {};
  }
};
const define = (_dependencies, factory) => factory(workbox);
runInNewContext(readFileSync(resolve(directory, 'sw.js'), 'utf8'), {
  define, self: {define, skipWaiting() {}}, URL, Headers, Response
}, {timeout: 1000});
assert.deepEqual(fallbacks, [new URL('index.html', site).href], 'Navigation fallback must use the deployed index');
console.log(JSON.stringify({result: 'PASS', base, manifestLanguage: manifest.lang,
  startUrl: new URL(manifest.start_url, manifestUrl).pathname,
  scope: new URL(manifest.scope, manifestUrl).pathname,
  navigationFallback: new URL(fallbacks[0]).pathname, precachedAssets: precached.size}));
