> 当前架构基线（2026-09-30）：公共阅读路径为 RSS -> Actions 采集与门禁 -> JSON 快照 -> GitHub Pages/Vue/PWA。原生 FastAPI/PostgreSQL 为独立可选运行路径，Docker 不是公共站点依赖。M1 增加按 BASE_URL 隔离的本地阅读状态、URL 筛选及来源报告页，不改数据库和现有 API。以下 V0.1 等章节为历史演进，不代表当前上线依赖。演进与契约见 [V1.0_PLAN.md](V1.0_PLAN.md) 和 [V1.0_DATA_CONTRACT.md](V1.0_DATA_CONTRACT.md)。

## 最新状态：2026-10-01 M3 容量修复回归

本节优先于以下旧阶段记录。当前本地 `0.5.0-alpha.1` / `M3-preview`，用户已采用有明确限制的 AI 评估出口。原生事件/趋势候选路由及本地 UI 已接通，常规 304 项测试和两模式构建/PWA 通过；原生数据库 2,001 篇 -> 有界 2,000 篇实测、原始深链和受控进程重启身份保持通过。

比较规则与历史注册表不变；增加投影内最多 100,000 项的纯特征缓存及保守候选上界，CPU 聚合在线程执行后再次验证 worker 完成标记。没有数据库迁移、全局新闻对象缓存、新基础设施或标签修改。

完整容量脚本仍被错误的精确事件数量断言阻断，待用户确认修正；首次 API 请求约 29 秒不代表生产 SLA。M3 不标记全量验收完成，V1.0.0 NOT RELEASED，未推送/部署。详见 [容量修复与回归](V1_M3_CAPACITY_RECOVERY.md)。

## 最新状态：2026-10-01盲审与纠错回归

当前仍为本地 `0.4.0-alpha.1` / `title-summary-v4`，**V1.0.0 BLOCKED / NOT RELEASED**。本节优先于下方较早阶段记录，旧测试数/漏合并数只代表当时证据。

代理已完成240对未见文章AI盲审（238明确、2不确定）；首次v3召回43.33%，v4调优后50%，原开发包v4为56.67%。AI来源、少量正例、非代表性以及调优后不再独立的边界均保留；不要求用户手动200对，也不伪造独立人工门禁。

本轮60快照＋70后端＋100前端=230项测试通过，类型检查、snapshot构建/PWA、合成拆分CLI和26文件代码＋数据本地精确还原通过。审核拆分保留第一组旧URL，必须完整历史成员证据，正常采集不自动纠错。新候选原采集时间保留为13:08Z，原文件与旧预览未覆盖。

公网13:46Z观测快照年龄7.177小时，两小时门禁失败。后台启动与旧生产刷新组合命令被执行策略整体拒绝，均未执行；当前v4真实HTTP/浏览器未验收。没有Git提交、推送、正式部署或标签。原生API事件接口与M3/M4/M5仍未完成，按原方案不越过M2出口。

详见 [本轮诊断与回归](V1.0_M2_HOLDOUT_20261001.md) 和 [正式发布门禁及恢复顺序](V1.0_RELEASE_GATE.md)。


## M2 本地候选，尚未部署

`0.4.0-alpha.1` 使用显式 `SnapshotProvider` / `ApiProvider`，生产启动不再覆盖全局 fetch。快照添加稳定文章、事件、发布机构标识和不可变代号；事件索引与来源报告绑定同一代号，读到不匹配文件时拒绝混用。原生 API 保持原契约，本轮没有实现 API 事件接口。

事件规则模块 `backend/app/services/event_index.py` 仅用 Python 标准库，由快照采集器调用，不变更数据库。采用同语种、48 小时时窗、数字/动作冲突拒合并和 complete-link 标题相似度；跨语种、自动合并/拆分纠正、AI 推理均不在已实现范围。事件注册表保留期最多 90 天，最多 5000 事件、10000 文章映射；快照只保留最近三代。

候选工作流从上次成功发布的 Pages 恢复有界事件状态，不依赖 Actions 缓存或无限 Git 历史。已有代号却缺失/损坏注册表时失败，不静默重置 ID。代码另存有 SHA-256 校验的有界归档，计划任务可复用兼容代码并覆盖新数据；代码推送仍完整构建。公开存储恢复、计划任务复用及真实 app+data 回滚尚未上线验证。

事件列表、详情、时间线、多机构筛选和缓存深链已本地实测。240 对真实报道人工评估包已生成，但没有人工标签，不能据此宣布 M2 或 V1.0 通过。

# Global News Architecture (V0.1)

2026-10-01候选补充：持久v1锚点不重置，比较层版本为title-rewrite-v2；显式审核合并输出有界、直接旧ID别名，正常采集不自动合并。前端详情解析别名并提示迁移，审核来源AI/human原样保留。11个旧深链在隔离候选实测可用；公开部署和拆分流程仍未验收。最新证据见 [V1.0_M2_RECALL_FIX.md](V1.0_M2_RECALL_FIX.md)。

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

Subsequent user approval adds a free publication mode: GitHub Actions fetches
configured official feeds and builds gated JSON, served with Vue on Pages.
`PAGES_DATA_MODE=snapshot` selects a same-origin read-only transport installed
before Vue mounts; native/API mode is unchanged. No always-on public backend
or database is claimed. Search/pagination operate on the bounded snapshot.
`PAGES_DEPLOY_ENABLED` still gates deployment; failed cloud collection keeps
the previous published version. `FREE_PAGES_DEPLOYMENT.md` supersedes the
public-backend prerequisite for this explicitly approved snapshot mode only.

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

### V0.2 UI localization: Simplified Chinese

The user-approved UI defaults to zh-CN without a language switch or new dependency.
Shared copy and display-label mappings live in `frontend/src/locales/zh-CN.ts`.
Only presentation is localized: publisher names, article titles/excerpts, API
paths, source IDs, filter values, and original timestamp fields stay unchanged.
Complete timestamps use the browser's local timezone and show the timezone.
Snapshot banners distinguish generation time, cached content, delayed updates,
and healthy/configured source counts. About text reflects the selected API or
snapshot build mode. No backend, collection, cache policy, or deployment change
is implied. See `UI_ZH_CN.md` for scope and pending acceptance work.

## 2026-10-01 原生事件投影候选

原生数据库文章/启用来源是权威数据；`NATIVE_EVENT_STORE_PATH` 为默认关闭的绝对持久目录。
复用事件索引；OS文件锁、进程异步锁、单文件不可变代次和原子指针保留三代及稳定ID注册表。
无数据库迁移和新依赖，不在2048字符的SyncState.value内塞入大JSON。完成worker时间为生成时间。
详见 `docs/V1.0_M2_NATIVE_API.md`。当前路由前缀接入失败，完整验收未通过；本地文件测试不代表托管持久性。

## 2026-10-02 当前候选与 M5 执行入口

当前版本为 `0.9.0-alpha.1`，非正式 V1.0.0。用户已接受 M2 版本绑定的 AI 评估出口；M3 完整 2,000 篇通用/密集容量回归通过，M4 采用无已确认免费额度的关闭路径。
319 项候选测试、类型检查、snapshot/API 构建及 /News/ PWA 路径通过。原生实测使用隔离合成数据库，不代表已托管公网 API。
新增独立 HTTP 观测工作流 observe-news.yml 和原代码+原数据的 restore-pages.yml；记录不改写采集时间、不以 Actions 成功充当新鲜度、不用重新采集冒充回滚。
七天观测绑定 0.9 候选，真实跨度至少 168 小时，336 个闭合半小时窗口、至少 95% 有效且数据年龄不超过两小时，缺测和失败均计入分母。
允许先部署非正式候选开始观测；真实配对回滚/前滚、设备/PWA 升级、性能和七天证据必须另行关闭，未满足不得打 V1.0.0 标签。
最新完整证据与顺序见 [V1_M5_CANDIDATE.md](V1_M5_CANDIDATE.md)；AI 关闭边界见 [V1_M4_AI_DISABLED.md](V1_M4_AI_DISABLED.md)。此前文档中的未修复前缀、M2 等待人工、M3 未开始/容量断言待修正均为历史状态。
