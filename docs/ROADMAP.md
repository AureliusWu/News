> 本文旧路线图自 2026-09-30 起作为历史记录保留。当前获授权执行的阶段、门禁与范围以 [V1.0_PLAN.md](V1.0_PLAN.md) 为准。M1 阅读核心回归已通过；M2 事件候选已实现，等待至少 200 对明确人工标注。M3/M4/M5 未开始，未发布 V1.0。

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
