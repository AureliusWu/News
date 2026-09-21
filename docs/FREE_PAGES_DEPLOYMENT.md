# Free GitHub Pages publication

Approved by the user on 2026-09-21. This is a V0.2 publication mode, not V0.3
development and not a claim that GitHub Pages runs the native Python backend.

## Architecture and cost boundary

- Keep the tested local FastAPI, Miniflux, PostgreSQL, worker and Docker/native configurations intact.
- A standard GitHub-hosted runner reads the existing official RSS/Atom configuration, normalizes public headlines and short summaries, and emits static JSON.
- GitHub Pages serves the existing Vue interface and JSON. An explicitly enabled, same-origin, GET-only snapshot transport preserves UI response contracts, pagination, search and filters. Other origins and assets are not intercepted.
- No new hosting account, credit card, public tunnel, paid runner, always-on database or paid API is required. No full article bodies, native credentials, private keys or internal Miniflux identifiers are published.
- No paid service or account spending setting is enabled by this implementation.

[GitHub's Actions billing documentation](https://docs.github.com/en/actions/concepts/billing-and-usage)
states that standard hosted runners are free for public repositories.
[Pages limits](https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits)
still apply, including bandwidth, site size and acceptable-use restrictions.
This is a personal, read-only news project, not a commercial transaction service.

## Publication controls

Set repository variables `PAGES_DATA_MODE=snapshot` and
`PAGES_DEPLOY_ENABLED=true` only after the candidate workflow passes.
`VITE_API_BASE_URL` is deliberately cleared in snapshot builds; localhost is
never used as a public backend. The previous API variable is ignored in this
mode. Do not enable API-mode publication without a real public HTTPS backend.

The workflow runs on `main` pushes, manual dispatch and at minutes 17 and 47
of each hour. Manual dispatch with `publish=false` builds/tests without deploying.
Setting `PAGES_DEPLOY_ENABLED=false` pauses publication and scheduled builds.

[Scheduled Actions can be delayed or dropped](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule).
Public-repository schedules may be disabled after 60 days without repository
activity. Do not add artificial keepalive commits to evade that rule; re-enable
the schedule through GitHub when needed. Do not promise exact 30-minute updates
or unattended uptime.

## Data contract and truthful freshness

The public snapshot contains at most 2,500 unique articles with original
publication dates in the preceding seven days. Search and filters cover that
published window, not an unlimited archive. Sources, publishers and original
links are retained. Summaries are plain text capped at 280 characters; titles
are capped at 500 characters. Missing publication dates are rejected, not
replaced with collection time. Unsupported adapters are reported rather than
counted as healthy.

The banner distinguishes snapshot generation time from article publication
times and explicitly says the edition is not live. It flags snapshots older
than two hours and offline/cache fallback. Cached snapshots older than 72 hours
are rejected. Cache denial or quota errors do not prevent online reading.
Pagination cursors are bound to the dataset hash and filters; a dataset change
returns a refresh-required error rather than mixing pages.

## Fail-closed gates

- At least 25 healthy feeds, 15 publishers, seven regions and two languages.
- At least 100 real, unique articles; newest publication within six hours.
- Safe links, canonical deduplication, original dates and bounded payload sizes.
- Collector tests, frontend tests and production build must pass before deployment.
- A failed run leaves the previous successful Pages deployment untouched; its timestamp is not relabeled as fresh.

Each run publishes `data/source-health.json` beside `data/news.json` and retains
a short-lived Actions evidence artifact. Native and Pages source health are
separate measurements: GitHub runners may receive different upstream responses
from the local proxy. The cloud report is authoritative for publication.

## Dependencies

Reuse mature RSS/HTML/HTTP/YAML libraries rather than writing a feed parser:
`feedparser 6.0.12` (BSD-2-Clause), `beautifulsoup4 4.14.3` (MIT),
`httpx 0.28.1` (BSD-3-Clause), and `PyYAML 6.0.3` (MIT).
Versions are pinned in `scripts/snapshot/requirements.txt`, installed in an
isolated environment rather than the native backend environment. News content
rights remain with publishers; library licenses do not grant permission to
republish full articles.

## Verification and rollback

Pre-change rollback commit: `cfe17aa8e1b5d1a40ebd29d2f71937486be077e0`.
First build a candidate with publication paused, then enable publication and
manually dispatch. Confirm the deployed commit, public data/health responses
and browser behavior for news, search, filters and pagination.

To pause, set `PAGES_DEPLOY_ENABLED=false`; the last deployed site stays online.
For code rollback, use a normal revert commit, not shared-history rewriting.
Reverting to API mode alone does not produce a usable public site without a
public HTTPS backend.

Operational run IDs, deployed SHA and public smoke results belong in the task's
release receipt. This guide describes the mechanism, not evidence that a
deployment has already succeeded.
