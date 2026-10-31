# Global News

<!-- project-badges:start -->
[![Version](https://img.shields.io/github/v/tag/AureliusWu/News?sort=semver&style=flat-square&label=version)](https://github.com/AureliusWu/News/tags) [![Build](https://github.com/AureliusWu/News/actions/workflows/deploy-gh-pages.yml/badge.svg?branch=main)](https://github.com/AureliusWu/News/actions/workflows/deploy-gh-pages.yml) [![Last commit](https://img.shields.io/github/last-commit/AureliusWu/News?style=flat-square)](https://github.com/AureliusWu/News/commits/main) [![License](https://img.shields.io/github/license/AureliusWu/News?style=flat-square)](LICENSE)
<!-- project-badges:end -->

当前正式版：`1.1.0`，状态为 `RELEASED_WITH_WARNINGS`。

移动端优先的全球新闻聚合 PWA。公开版本使用 GitHub Actions 定时生成新闻快照并部署到 GitHub Pages，不依赖常驻公网 API。

[访问网站](https://aureliuswu.github.io/News/) · [v1.1.0 Release](https://github.com/AureliusWu/News/releases/tag/v1.1.0)

## 核心能力

- 地区、来源和关键词筛选。
- 事件聚合、事件详情与报道时间线。
- 事件关注、收藏、筛选方案与本地备份。
- GitHub Actions 定时生成和发布静态新闻快照。
- 独立 freshness observer 监测线上数据新鲜度；工作流成功不等于数据新鲜。
- PWA 安装与 GitHub Pages 部署。

## 本地开发

```bash
# 前端
cd frontend
npm install
npm test
npm run dev

# 后端（可选开发路径）
cd backend
python -m pip install -r requirements.txt
pytest
```

环境变量见 `.env.example`。

## AI / 维护者入口

修改前先读 [AGENTS.md](AGENTS.md)。当前发行事实、风险接受与未完成验收见 [V1.1.0_HANDOFF.md](docs/V1.1.0_HANDOFF.md) 和 [V1.1.0_RELEASE_WAIVERS.md](docs/V1.1.0_RELEASE_WAIVERS.md)。

- 不借用旧版本豁免或验收结果给新版本放行。
- 新闻源配置化，不把来源硬编码进业务逻辑。
- 数据库变更通过 Alembic 管理。
- 当前公开形态以静态快照为主；历史 Docker / PostgreSQL 路径仍保留在代码和文档中。
- 历史发布、逐轮验收和旧版本证据继续留在 `docs/` 与 Release，不回填进 README。

## License

MIT License。