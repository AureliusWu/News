# M5 isolated browser and startup comparison plan

This change adds test infrastructure only. It does not publish a new application,
change acceptance thresholds, release V1.0.0, or operate Cloudflare.

## Fixed scope

- Baseline: `5e55cf7d5a5014bc4c55b7f9aad18bbede966380`.
- Candidate: `3a3e0dcf0baf39ceacd0d4a65e015a80b3761333`.
- One captured public news response and its generation-bound event/source-health
  files are copied byte-for-byte to both builds. Hashes and source revisions are
  included in the manifest and archived with the built clients.
- Chromium and Firefox run online news, bookmark persistence, event navigation,
  detail reload and 390px layout checks with fresh runner-owned profiles.
- Chromium additionally tests cached offline reload and a real same-origin
  transition from the older candidate to the newer bundle. Storage is not cleared
  and Service Worker activation is not forced with a synthetic skipWaiting call.
- Firefox Service Worker cases are explicitly skipped, not counted as passes.
- The performance diagnostic alternates AB/BA runs, three cold samples per arm
  per device preset, using the same frozen JSON. Third-party HTTPS resources are
  excluded from BOTH arms to isolate application startup. Every sample remains.
- The loopback performance diagnostic is not the production/CDN first-screen
  gate. It cannot replace existing public failures, interaction measurements,
  physical-phone evidence or the full older-client matrix.

## Execution boundary

Only manual GitHub Actions dispatch runs this workflow. It has read-only repository
permissions and no Pages deployment job. Runtime guards reject browser/server
execution outside Linux GitHub Actions. Only child preview processes owned by the
test fixture are stopped. The previously blocked Windows start/stop and failure-
injection acceptance remains a separate unresolved item.

## Evidence and remaining gates

The workflow archives frozen inputs, both clients, full Playwright reports,
failure traces/screenshots, preview logs, all Lighthouse reports and a comparison
summary. A successful infrastructure run is not formal release approval.

Production seven-day cadence, mobile performance tails, real interaction, real
phone use and outstanding local-runtime evidence are unchanged. The ambiguous
phone reply is not accepted as a device/browser/operation receipt.

Official references: [Playwright CI](https://playwright.dev/docs/ci-intro),
[offline emulation](https://playwright.dev/docs/api/class-browsercontext#browser-context-set-offline),
[Service Worker support and activation](https://playwright.dev/docs/service-workers).
