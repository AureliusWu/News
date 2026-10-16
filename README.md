> 当前状态（2026-10-16）：**V1.0.0 已正式发布，状态为 RELEASED_WITH_WARNINGS（用户明确批准本次发布豁免）**。这不代表原始验收门槛全部通过：七天覆盖、生产性能与真实交互、真实手机、完整旧客户端/PWA 矩阵和 Windows 完整启停/故障注入仍按原始结果记录。356 项自动化回归、8 项浏览器测试及公网资源一致性检查已通过，另有 2 项 Firefox 离线/升级测试按范围跳过。网站继续使用 GitHub Pages 定时快照，不需要常驻公网 API 或 Docker。
>
> [访问网站](https://aureliuswu.github.io/News/) · [V1.0.0 发布与原始证据附件](https://github.com/AureliusWu/News/releases/tag/v1.0.0) · [最终交接](docs/V1.0.0_HANDOFF.md) · [发布豁免清单](docs/V1.0.0_RELEASE_WAIVERS.md)。标签、已测和已部署代码均为 `31cf95d6ae471bb961eb5b85a334ec78f4cce260`。下文较早版本记录仅作历史参考。

# Global News

Global News 是一个移动端优先的全球新闻聚合 PWA。当前公开形态以静态应用包 + 定时新闻快照运行，不依赖公网常驻实时 API。

## Product snapshot

- 当前候选：`0.9.0-alpha.1`，非正式 V1.0。
- 地区、来源筛选与关键词搜索。
- 新闻事件聚合、事件详情与报道时间线。
- 趋势/热度能力进入 V1.0 候选。
- GitHub Actions 定时生成并发布新闻快照。
- 独立 freshness observer 记录线上数据新鲜度，不以工作流成功代替数据新鲜度。
- PWA 支持与 GitHub Pages 部署。

## Tech stack

- Frontend: Vue 3 + TypeScript + Vite + Pinia + Vue Router + Tailwind CSS + vite-plugin-pwa
- Backend: FastAPI + Pydantic + SQLAlchemy + Alembic + httpx + pytest
- Database: PostgreSQL / SQLite verification paths
- Infrastructure: GitHub Pages + Actions snapshots；Docker / Compose 保留用于本地与历史后端路径

## Quick Start

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

## V1.0 status

当前以 `docs/V1.0_HANDOFF.md` 为事实入口。0.9 候选已经进入公开观察阶段，但 V1.0.0 标签和正式发布必须等待剩余 M5 门禁完成。

早期 V0.1.x–V0.5 路线、Docker/PostgreSQL 恢复过程和旧验收记录保留在仓库文档中，不再作为当前版本状态来源。

## License

MIT License.

## GitHub Pages 部署（前端）

- 自动部署工作流：`.github/workflows/deploy-gh-pages.yml`
- `main` 推送及计划任务均可驱动候选/快照发布；具体触发和复用逻辑以工作流文件为准。
- 部署地址：`https://AureliusWu.github.io/News/`
- 若需要自定义 API 地址，可在仓库设置里配置 `VITE_API_BASE_URL`。

### 手动触发

- 在 GitHub 仓库页面执行 Actions -> `Deploy Frontend to GitHub Pages` -> `Run workflow`。
