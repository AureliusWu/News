> 当前入口（2026-10-25）：V1.0.0 已于 2026-10-16 按用户批准的五类豁免正式发布，状态为 RELEASED_WITH_WARNINGS；证据见 [V1.0.0_HANDOFF.md](V1.0.0_HANDOFF.md)。用户已授权执行 [V1.1.0：稳定更新与持续阅读](V1.1.0_PLAN.md)，进度见 [V1.1_EXECUTION.md](V1.1_EXECUTION.md)。下方为历史路线图，不代表当前状态。

# Global News Roadmap

- V0.1.2 Recovery / Verification
  - 目标：完成 Docker/数据库/Alembic/同源 API 与健康检查可复现验收。
  - 当前状态：本地配置、容器链路与 Smoke 复验进行中；待 Docker 健康链路与数据库链路最终结果确认。
- V0.1 Skeleton
  - Frontend/Backend/PWA/Postgres 骨架
  - 健康检查与基础文档
- V0.2 Feed
  - 引入 Miniflux、RSSHub 与 sources.yaml
  - 添加同步 Worker 获取真实新闻
- V0.3 Globalization
  - Region/Category/Language/搜索
- V0.4 Story
  - URL 去重与聚类
- V0.5 Breaking & Trends
  - GDELT 信号与 Breaking 打分
- V1.0 AI Capabilities
  - Summary / Translation / Multi-source synthesis
