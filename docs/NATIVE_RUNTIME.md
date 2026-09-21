# Native Ubuntu runtime (V0.2.0)

## Decision and scope

On 2026-09-13 the user approved replacing the Docker-dependent local runtime with
WSL2 Ubuntu native services. Docker Desktop is not required by this deployment.
The existing Compose files and Docker volumes are retained, not migrated, reset,
or deleted. This is a new isolated database deployment; old Docker data is not
implicitly copied. WSL2 still uses lightweight virtualization.

The previous seven-container gate is superseded by seven native-service gates
for this deployment only. Feed coverage, real-data, API, frontend, persistence,
restart and test requirements are unchanged. A successful installer is not an
E2E pass. No Git commit, push, cloud purchase, or production cutover is implied.

## Quick start (PowerShell, repository root)

```powershell
.\scripts\Native.ps1 -Action Install
.\scripts\Native.ps1 -Action Status
.\scripts\Native.ps1 -Action Logs
.\scripts\Native.ps1 -Action Stop
.\scripts\Native.ps1 -Action Start
```

Requirements: Windows WSL2, Ubuntu 24.04 with systemd, outbound HTTPS, and a
compatible Windows Node/npm installation for the existing frontend. Installation
uses the distro's root account, but application services run as dedicated
unprivileged accounts. No global Windows Python/Node downgrade is performed.
The installer currently supports Linux x64. `-Distro` selects the distribution.

The first installation downloads dependencies and builds the separate RSSHub
service. Official RSS sources remain the default. Browser-dependent RSSHub
routes are not promised: Chromium/Playwright browser downloads are skipped.

## Runtime

| Service | Manager | Loopback port | Data/config |
|---|---|---|---|
| News PostgreSQL 16 | postgresql@16-news | 55432 | /var/lib/postgresql/16/news |
| Miniflux PostgreSQL 16 | postgresql@16-newsminiflux | 55433 | /var/lib/postgresql/16/newsminiflux |
| Miniflux 2.3.3 | news-miniflux | 8081 | /etc/global-news/miniflux.env |
| RSSHub | news-rsshub | 1200 | separate /opt/global-news/vendor directory |
| FastAPI | news-backend | 8000 | /etc/global-news/app.env |
| Sync worker | news-worker | none | same app database and Python environment |
| Nginx / Vue PWA | news-frontend | 8080 | /var/lib/global-news/frontend |

All TCP listeners are intended to bind to loopback. Miniflux and News have
separate PostgreSQL clusters, roles and databases. HTTP authentication to
Miniflux stays on loopback; no credentials enter the frontend. The API proxy
forwards only `/api/v1/`, `/api/health` and `/api/ready`.

Random native credentials are generated once and stored under root-only
`/etc/global-news/` with file mode 0600. The repository `.env` is unchanged.
Back up native credentials with the two database backups, never into Git.

The installer uses Python 3.12 and the existing pinned backend requirements.
Miniflux and Node downloads have pinned SHA-256 checks. Node is 24.21.0 LTS;
RSSHub is pinned to commit `67305a500b0c90fba23a9155440ed28d2b011a6b`, with its
frozen pnpm lockfile and pnpm 10.34.5. RSSHub remains an independent AGPL-3.0
application outside this repository, not copied into the business backend.

## Development and verification

```powershell
.\scripts\Native.ps1 -Action Build
.\scripts\Native.ps1 -Action Restart
.\scripts\Native.ps1 -Action TestBackend
.\scripts\Native.ps1 -Action ValidateSources
.\scripts\Native.ps1 -Action VerifyPipeline
```

Backend code runs from the current checkout. Restart applies Python changes;
the backend runs Alembic upgrade before starting. Build deploys the frontend
with base `/` and same-origin API access. GitHub Pages builds remain separate
and require their own `/News/` base and public API URL.

Start keeps WSL alive using a hidden, PID/start-time-tracked `wsl sleep infinity`
process. Stop shuts down only this project's seven units and its own keeper.
It does not terminate the distribution or other user processes. This is not a
Windows-login auto-start task and does not keep a sleeping/off PC online.

## Hosting and rollback

Local service access is not public deployment. GitHub Pages cannot execute the
Python API or polling worker. Production needs a separately provisioned server,
HTTPS, backups, public API configuration and its own acceptance checks.

To return to the old deployment, stop native services, then use the retained
Compose configuration after separately resolving Docker. The native databases
remain on disk. Never use volume deletion or WSL unregister as rollback.

Official references:

- [Miniflux manual installation](https://miniflux.app/docs/binary_installation.html)
- [Miniflux configuration](https://miniflux.app/docs/configuration.html)
- [Miniflux release](https://miniflux.app/releases/2.3.3.html)
- [RSSHub pinned source](https://github.com/DIYgod/RSSHub/tree/67305a500b0c90fba23a9155440ed28d2b011a6b)
- [WSL systemd](https://learn.microsoft.com/en-us/windows/wsl/systemd)
- [GitHub Pages scope](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages)

## 2026-09-16 verification update

The seven native services, frontend/backend tests, production build, real-news
API lineage, and restart persistence checks passed locally. The database
snapshot held 821 distinct articles; source coverage passed with 36 healthy
feeds, 25 publishers, 9 regions and 5 languages. See `V0.2_HANDOFF.md` and
`V0.2_SOURCE_HEALTH.md` for dated evidence and acceptance boundaries.

Important: the optional proxy transport works, but its PowerShell process
ownership/status logic is not accepted. JSON timestamp conversion causes a
false process mismatch and repeated starts can overwrite the tracked PID.
Do not rely on repeated Start/Stop operations for that optional tunnel until
the management defect in `V0.2_HANDOFF.md` is repaired. Docker data was untouched.

## 2026-09-21 local regression closure

This section supersedes the earlier partial proxy-lifecycle acceptance notes.
`scripts/Test-ProxyLifecycle.ps1` passed all 16 lifecycle and metadata fault
assertions on September 17 and again on September 21. It uses an isolated
metadata fixture, verifies exact process ownership, exercises real Stop/Start
and lock contention, and checks RSS HTTP 200 after restart. It never injects
foreign metadata into the live PID file or kills unrelated processes.

On September 21 normal Start restored all seven services from an inactive
session. Backend tests: 70 passed. Frontend tests: 20 passed. Production build:
PASS. The final pipeline's 18 checks passed with 1,550 unique articles; source
coverage passed with 36 healthy feeds, 25 publishers, 9 regions and 5 languages.
Windows host requests to the frontend, health API and news API returned HTTP 200.

The deliberate tunnel interruption produced 23 temporary feed failures. Normal
tunnel recovery plus targeted Miniflux refresh cleared them; both failed and
recovered snapshots remain under `artifacts/`. Do not interpret this assisted
recovery as proof of automatic reconnection or overnight operation.

Local URL: <http://127.0.0.1:8080/>. GitHub code synchronization is authorized;
website publication is not. `PAGES_DEPLOY_ENABLED=false` keeps the Pages deploy
job skipped. A public HTTPS backend is still required for a future publication.
See `V0.2_HANDOFF.md` and `V0.2_SOURCE_HEALTH.md` for dated evidence and limits.

## 2026-09-17 follow-up (historical; superseded by September 21 above)

The optional proxy controller now compares typed UTC timestamps and verifies
its complete project-specific SSH process identity. Repeated Start and Status
checks passed; a normal Native Start restored all seven services. The earlier
status false negative is fixed in code and in its reproduced live scenario.

The broader Stop/Start and fault-injection test batch was rejected by execution
policy before it ran. Recovery, foreign-owner rejection and lock contention
have not received live acceptance; do not describe the full lifecycle as closed.

Backend 70/70, frontend 20/20 and the production build passed again. After an
explicit Miniflux refresh, the 11:51 +08:00 snapshot held 1300 unique articles,
with the latest published at 11:38:03 today. The source gate remains 36 healthy
feeds from 25 publishers across 9 regions and 5 languages. This was assisted
cold-start recovery, not an overnight unattended or public-deployment test.
See V0.2_HANDOFF.md for separate failed-before-refresh and passed-after-refresh
evidence, plus the remaining acceptance limits.
