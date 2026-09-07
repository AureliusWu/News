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
