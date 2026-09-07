# V0.1 Dependency Research

## Core Dependency Decisions

| Project | GitHub | License | Use in this project | Dependency type | Why |
|---------|--------|---------|--------------------|----------------|-----|
| Vue | https://github.com/vuejs/core | MIT | 核心前端框架 | Direct | 现代组件化生态与社区成熟度。 |
| Vite | https://github.com/vitejs/vite | MIT | 前端打包与开发服务器 | Direct | 快速 HMR 与构建体验。 |
| vite-plugin-pwa | https://github.com/vite-pwa/vite-plugin-pwa | MIT | PWA 基础能力 | Direct | 官方推荐方式，避免手工 SW 实现。 |
| FastAPI | https://github.com/fastapi/fastapi | MIT | 后端 API 框架 | Direct | 简洁高性能、异步友好。 |
| SQLAlchemy | https://github.com/sqlalchemy/sqlalchemy | MIT | ORM/DB Session | Direct | 统一数据库抽象，配合 Alembic 迁移。 |
| Alembic | https://github.com/sqlalchemy/alembic | MIT | 数据库迁移 | Direct | 与 SQLAlchemy 完整协同。 |
| PostgreSQL | https://github.com/postgres/postgres | PostgreSQL License | 独立服务 | 数据持久化数据库 | 可靠、支持未来复杂查询。 |
| Miniflux | https://github.com/miniflux/v2 | Apache-2.0 | 规划在 V0.2 独立接入 | 独立服务 | 成熟 RSS/Atom/JSON 抓取服务。 |
| RSSHub | https://github.com/DIYgod/RSSHub | MIT | 规划在 V0.2 独立接入 | 独立服务 | 覆盖无 feed 站点的 RSS 生成。 |
| GDELT | https://www.gdeltproject.org/ | Mixed usage terms | 规划在 V0.5 之后 | 外部服务 | 提供热点趋势信号。 |

> 注：V0.1 只做骨架，不在本阶段接入 Miniflux、RSSHub、GDELT。
