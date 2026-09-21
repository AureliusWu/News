# Global News Architecture (V0.1)

```text
+-----------------+      +-----------------+      +-----------------+
|     Frontend    |----->|     Backend     |----->|   PostgreSQL     |
| (Vue + PWA)     |      | (FastAPI)       |      | (Docker Compose) |
+-----------------+      +-----------------+      +-----------------+
       |                        |
       | HTTPS/API               | DB Session, Alembic
       v                        v
+-----------------+      +-----------------+
| Service Worker  |      | Health Endpoints |
| (Vite PWA)      |      | /health,
| Offline shell   |      | /api/v1/health    |
+-----------------+      +-----------------+
```

V0.1 保持单体服务形态，只保留最小可运行骨架。

## V0.2 native runtime status, 2026-09-16

The current local route is WSL2 Ubuntu/systemd, not Docker Desktop. Official
RSS feeds flow through Miniflux, the ingestion worker, the dedicated News
PostgreSQL database, FastAPI, and Nginx/Vue. Dedicated native clusters do not
reuse Docker volumes. RSSHub is available as an optional adapter but all 36
healthy feeds in this snapshot are official RSS.

The Windows proxy is reached through a loopback-only SSH reverse forward;
credentials and the private key are outside the checkout. Its transport
passed, but a process-ownership timestamp defect remains open. The full local
acceptance decision and public-deployment boundary are in `V0.2_HANDOFF.md`.
This dated section supersedes earlier Docker-only local-operation assumptions,
not the historical verification results of previous versions.

### 2026-09-21 acceptance and publication boundary

The native topology is unchanged. The isolated-fixture proxy regression now has
16/16 passing lifecycle assertions, including Stop/Start and fault recovery;
the earlier blocked-batch note is historical. Seven native services, backend
and frontend tests, the production build, Windows loopback access, source
coverage and real-news pipeline checks passed on September 21. Detailed dated
results and remaining operational limits are in `V0.2_HANDOFF.md`.

GitHub source synchronization is separate from website publication. The Pages
workflow deploy job runs only when `PAGES_DEPLOY_ENABLED` is exactly `true`;
the repository variable is currently `false` by user instruction. Paused runs
build without a public API target but do not update the live Pages site. A
future publication must provide a public HTTPS backend, never localhost.

### 2026-09-17 correction to the proxy note (historical)

The process-ownership timestamp defect mentioned above has been patched in the
PowerShell controller and reproduced Start/Status checks now pass. Exact process
identity and exclusive lifecycle locking were added. The expanded stop/recovery
fault-injection batch was blocked before execution, so complete lifecycle
acceptance remains open. The native service topology and storage isolation did
not change. Current evidence is in V0.2_HANDOFF.md.
