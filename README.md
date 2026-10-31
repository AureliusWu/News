> 当前状态（2026-10-26）：**V1.1.0 已按用户明确批准的风险接受方案正式发布**，固定应用源码 `20e630e20727dc3c243747c27b0101d9ac9e336e`，`formal_release=true / RELEASED_WITH_WARNINGS`。本轮 417 项回归和 28 项浏览器用例通过，2 项 Firefox SW 范围跳过；七天观察与设备验收仍未完成，按本版新批准豁免并继续监测。见 [交接](docs/V1.1.0_HANDOFF.md)、[风险接受记录](docs/V1.1.0_RELEASE_WAIVERS.md)、[正式 Release 与证据附件](https://github.com/AureliusWu/News/releases/tag/v1.1.0)。
>
> 历史正式版本（2026-10-16）：**V1.0.0 已正式发布，状态为 RELEASED_WITH_WARNINGS（用户明确批准该次发布豁免）**。356 项回归、8 项浏览器测试及 2 项范围跳过属于旧版本证据，不能用作 V1.1.0 放行。公开网站使用 GitHub Pages 定时快照，不需要常驻公网 API 或 Docker。
>
> [访问网站](https://aureliuswu.github.io/News/) · [V1.0.0 发布与原始证据附件](https://github.com/AureliusWu/News/releases/tag/v1.0.0) · [旧版交接](docs/V1.0.0_HANDOFF.md) · [旧版发布豁免清单](docs/V1.0.0_RELEASE_WAIVERS.md)。旧正式应用源码为 `31cf95d6ae471bb961eb5b85a334ec78f4cce260`，其豁免不转用于新版。

# Global News

<!-- project-badges:start -->
[![Version](https://img.shields.io/github/v/tag/AureliusWu/News?sort=semver&style=flat-square&label=version)](https://github.com/AureliusWu/News/tags) [![Build](https://github.com/AureliusWu/News/actions/workflows/deploy-gh-pages.yml/badge.svg?branch=main)](https://github.com/AureliusWu/News/actions/workflows/deploy-gh-pages.yml) [![Last commit](https://img.shields.io/github/last-commit/AureliusWu/News?style=flat-square)](https://github.com/AureliusWu/News/commits/main) [![License](https://img.shields.io/github/license/AureliusWu/News?style=flat-square)](LICENSE)
<!-- project-badges:end -->

Global News 是一个移动端优先的全球新闻聚合 PWA。当前公开形态以静态应用包 + 定时新闻快照运行，不依赖公网常驻实时 API。

## Product snapshot

- 当前正式版：`1.1.0`，标签 `v1.1.0`，风险接受发布，未完成项公开保留。
- 地区、来源筛选与关键词搜索。
- 新闻事件聚合、事件详情与报道时间线。
- 事件关注及新增报道、命名筛选方案、本地收藏与备份。
- GitHub Actions 定时生成并发布新闻快照。
- 独立 freshness observer 记录线上数据新鲜度，不以工作流成功代替数据新鲜度。
- PWA 支持与 GitHub Pages 部署。

## Tech stack

- Frontend: Vue 3 + TypeScript + Vite + Pinia + Vue Router + Tailwind CSS + vite-plugin-pwa
- Backend: FastAPI + Pydantic + SQLAlchemy + Alembic + httpx + pytest
- Database: PostgreSQL / SQLite verification paths
- Infrastructure: GitHub Pages + Actions snapshots；Docker / Compose 保留用于本地与历史后端路径

## Quick Start

直接打开[公开网站](https://aureliuswu.github.io/News/)即可阅读，无需 Docker。以下容器步骤仅用于可选本地后端路径；原生开发命令见 Local development，历史启停边界见本版交接。

1. Copy environment file:

```bash
cp .env.example .env
```

2. Build and run:

```bash
docker compose up --build
```

3. Open:

- Frontend: http://localhost:8080
- Health: http://localhost:8000/health

## Local development

- Backend dev dependencies:

```bash
cd backend
python -m pip install -r requirements.txt
```

- Frontend deps:

```bash
cd frontend
npm install
npm run dev
```

## Test

- Backend:

```bash
cd backend
pytest
```

- Frontend:

```bash
cd frontend
npm test
```

## Environment Variables

See `.env.example`.

## 版本与验收状态

当前以 [V1.1.0_HANDOFF.md](docs/V1.1.0_HANDOFF.md) 为事实入口；正式版本已部署，七天观察和真实手机/已安装 PWA 按本版明确批准列为未完成并继续监测。风险接受不等于原门禁通过，V1.0.0 的旧批准没有转用于本版。

早期 V0.1.x–V0.5 路线、Docker/PostgreSQL 恢复过程和旧验收记录保留在仓库文档中，不再作为当前版本状态来源。

## License

MIT License.

## GitHub Pages 部署（前端）

- 自动部署工作流：`.github/workflows/deploy-gh-pages.yml`
- `main` 推送及计划任务均可驱动候选/快照发布；具体触发和复用逻辑以工作流文件为准。
- 部署地址：`https://AureliusWu.github.io/News/`
- 当前 snapshot 模式不使用 `VITE_API_BASE_URL`，失效的 localhost 仓库变量已移除；仅在另行启用 API 模式且有可用公网 HTTPS 后端时配置。

### 手动触发

- 在 GitHub 仓库页面执行 Actions -> `Deploy Frontend to GitHub Pages` -> `Run workflow`。
