# V0.2 Pages PWA path correction

## Confirmed publication defect

The September 21 public snapshot build registered `/News/sw.js`, but its
navigation fallback was `/index.html`. The generated manifest also used `/`
for its start URL and scope, and root-level icon URLs. The CLI `--base=/News/`
override did not update strings calculated earlier from `BASE_PATH` in the
Vite configuration. Workbox rejects a navigation fallback that is not in its
precache; this can prevent replacement of an older active service worker.
This is evidence of a publication defect, not proof of every visitor's cache
state or the sole cause of a particular browser's old page.

## Approved repair

Manifest start URL, scope, and icons now use paths relative to the manifest.
The navigation fallback is relative to the service worker URL. This supports
both root deployments and project subpaths without hardcoding the repository
name. Manifest display text and language now match the Chinese UI.

`scripts/verify-pwa-build.mjs` checks the generated manifest, icon artifacts,
registration URL/scope, and fallback membership in the generated precache.
It evaluates the generated registration with non-networking Workbox stubs;
it does not claim to simulate browser installation or offline behavior.
The Pages workflow runs this gate after building and before uploading.

```powershell
node scripts/verify-pwa-build.mjs frontend/dist /News/
```

No browser storage is broadly cleared, and no homepage or other application
cache is deleted. Existing `autoUpdate`, `skipWaiting`, and `clientsClaim`
behavior is retained. A returning visitor may need to reload after the corrected
worker has downloaded and activated. The publication receipt must distinguish
HTTP/artifact checks from actual browser and returning-client checks.

Reference: [Workbox precaching](https://developer.chrome.com/docs/workbox/modules/workbox-precaching).
