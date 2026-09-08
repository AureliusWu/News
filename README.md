# Global News

Global News is a V0.1.1 verification-ready skeleton for a global real-time news aggregator PWA.

## Product snapshot

- App name: Global News
- Mobile-first timeline shell
- Backend health status integration
- PostgreSQL and deployment bootstrapping

## Tech stack

- Frontend: Vue 3 + TypeScript + Vite + Pinia + Vue Router + Tailwind CSS + vite-plugin-pwa
- Backend: FastAPI + Pydantic + SQLAlchemy + Alembic + httpx + pytest
- Database: PostgreSQL
- Infrastructure: Docker + Docker Compose

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

## Roadmap

- V0.1.1 Verification / Stabilization
  - 版本目标：本地验收完成（后端健康检查、前后端测试、PWA 构建与本机联调）。  
  - 当前状态：已完成关键命令复现，环境阻断项见 `docs/V0.1.1_VERIFICATION.md`。

- V0.2: integrate Miniflux/RSSHub and real feed sync worker.
- V0.3: region/category/search capabilities.
- V0.4: story clustering.
- V0.5: breaking/trending logic.
- V1.0: AI summary and translation.

## License

MIT License.
## GitHub Pages 部署（前端）

- 自动部署工作流：`.github/workflows/deploy-gh-pages.yml`
- 触发方式：向 `main` 分支推送后自动构建并发布。
- 部署地址：`https://AureliusWu.github.io/News/`（仓库名为 `News` 时）
- 若你需要自定义 API 地址，可在仓库设置里新增变量：`VITE_API_BASE_URL`

### 手动触发

- 在 GitHub 仓库页面执行 Actions -> `Deploy Frontend to GitHub Pages` -> `Run workflow`。
