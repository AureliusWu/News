# M3: explainable activity and bounded promotions

Candidate version: `0.5.0-alpha.1`. Stage: `M3-preview`. Formal release: **false**.

## Scope

The existing news/article/event contracts, original text, stable event IDs, aliases, filters and original-publication timeline remain intact. Default event sorting remains latest original publication. Optional hot and publisher-count views are added without deleting original reports.

The backend exposes `/api/v1/trends` from the same native database snapshot. The static frontend derives the same report without a paid service, Docker or a new database schema. Both implementations consume `backend/config/event_promotions.json`; the cross-runtime parity helper uses synthetic fixtures only.

## Score

Score time is the actual snapshot `generated_at`, not request time. The recent window is `(as_of - 6h, as_of]`; the previous window is `(as_of - 12h, as_of - 6h]`.

| Component | Formula / maximum |
| --- | --- |
| Activity | `min(max(recent_capped - previous_capped, 0) / 8, 1) * 40` |
| Publisher diversity | `min(recent_publishers / 4, 1) * 40` |
| Recency | `max(0, 1 - newest_publication_age_hours / 6) * 20` |

Components are rounded to one decimal, then their sum to one decimal. Each publisher contributes at most two articles per window. Same-publisher normalized URLs are deduplicated after fragment/common `utm_*`, `fbclid`, `gclid` removal and query ordering. This is not a general content-syndication detector. Multiple publishers do not prove editorial independence.

Valid old evidence can score zero; missing publisher/date/URL or future-only evidence scores `null`, not zero. Invalid/future/duplicate counts are disclosed. Hot sorting is deterministic by pin priority, score, latest publication and event ID. Heat is report activity, never truth or credibility.

## Promotions

Rules are empty by default. At most 100 rules / 64 KiB are permitted. A rule needs an active event ID, unique ID, explicit `maintainer` or `ai-reviewed` origin, pin/exclude action, bounded priority, reason, reference, UTC-offset timestamps and expiry within seven days. Conflicting event rules are rejected. Feed titles and summaries are never interpreted as configuration instructions.

Rules are evaluated at the current clock. More than two hours of snapshot age, or more than five minutes in the future, disables promotions. Exclusion applies only to the hot view; latest view and original details remain accessible. Pins do not alter the score. Retired aliases do not silently retarget a rule; maintenance must explicitly name the current event ID.

Native generation keys now include the app version for new bundles, while retaining the reader for legacy generations. This avoids returning previous-version metadata when data content has not changed and does not reset the event registry.

## Acceptance

Implementation is written; gate results will be appended from actual commands. No V1.0.0 tag, production candidate push or deployment is claimed here. M2 uses the user-approved AI exit documented in `V1_M2_AI_EVALUATION_EXIT.md`; independent human gold is not claimed.

Remaining sequential work: complete M3 regression, then M4 optional AI enrichment with safe fallback/provenance and M5 release/capacity/production acceptance. Seven-day freshness and real-device/PWA upgrade gates remain intact.

## Actual regression evidence, 2026-10-01

Artifact directory: `artifacts/v1-m3-ai-exit-20261001/`.

| Gate | Actual result |
| --- | --- |
| Backend full regression | FAIL at collection: new route imports nonexistent `app.db.session`; actual module is `app.core.db` |
| Frontend regression | PASS, 123 / 123 across 9 files |
| Snapshot regression | PASS, 60 / 60 |
| Frontend application + Node type checks | PASS |
| Python / TypeScript scorer parity | PASS, 14 synthetic cases |
| Frontend builds | Not run this round |
| Real API / browser M3 smoke | Not run; backend import failure blocks startup |

The incorrect import is a newly introduced implementation error, not Docker, permissions or an external-service blocker. Both the new route and the new route test contain this path. It was disclosed to the user; no silent repair, commit, push or candidate deployment occurred. M3 is **not accepted** until this defect is corrected and the outstanding gates pass.

Existing production and unrelated working-tree changes are preserved. The approved M2 AI exit remains valid independently of this M3 implementation failure.

## Import recovery and actual runtime evidence, 2026-10-01

This section supersedes the earlier import-blocked status only. The user authorized the repair by requesting continuation. The new route and route test now import `get_db` from the actual `app.core.db` module.

Current status: **FUNCTIONAL_PREVIEW_VERIFIED_CAPACITY_BLOCKED**. M3 is not fully accepted. Formal release remains false.

| Gate | Actual result |
| --- | --- |
| Backend full regression after repair | PASS, 116 / 116; 2,829 Python 3.14 / dependency deprecation warnings |
| Frontend regression | PASS, 123 / 123; frontend source unchanged since that run |
| Snapshot regression | PASS, 60 / 60 |
| Unique regression tests | 299 total; parity scenarios are counted separately |
| Application + Node type checks | PASS |
| Snapshot and API builds | PASS, both `0.5.0-alpha.1`, base `/News/` |
| Snapshot PWA path gate | PASS: zh-CN, start/scope `/News/`, fallback `/News/index.html` |
| Synthetic cross-runtime score parity | PASS, 14 cases |
| Native snapshot / events / trends / detail / versioned asset | HTTP 200 on 80 eligible synthetic articles |
| Python / frontend parity on actual HTTP fixture | PASS, all 80 event scores |
| Real browser | PASS for list, default latest, hot sort, formula, AI limits, load-more, detail and original link |
| New-client browser detail refresh | PASS after initial site load; not an old-client cache-upgrade test |
| Plain HTTP deep-link in temporary acceptance harness | 404; not accepted as server-side SPA fallback proof |
| 2,000-article native capacity | FAIL: first snapshot request exceeded 45 seconds |
| Commit / push / candidate deployment | Not performed |

### Capacity failure, not an external blocker

The isolated fixture held 2,001 synthetic database articles to exercise the 2,000-article projection cap. After completion-marker setup, the first native snapshot request timed out before returning any response. The owned process had consumed 132.53125 CPU seconds at teardown, with approximately 111 MB working set. `/api/v1/trends` was not reached in that attempt, so this evidence does not implicate the M3 heat scorer itself. It points to the native snapshot/aggregation path; profiling is required before asserting a specific function-level cause.

The identity-checked, agent-owned process was stopped; no unrelated server was stopped. `capacity-timeout.json` retains the failure. No successful 2,000-article result, baseline-relative performance improvement or approved latency-target gate is claimed.

A separate, non-destructive fixture cutoff then retained 80 eligible articles solely for functional testing. This smaller success **does not replace the capacity failure**. The database still contains 2,001 synthetic rows. No real news or production database was modified.

### Bounded actual API / browser evidence

Generation: `d79967863f5986d8f068f019`. Snapshot time: `2026-10-01T14:59:32.761257+00:00`. The API and frontend used the same candidate API build and generation.

There were 80 events, including 56 eligible hot events. The browser displayed the explicit 240/238 AI sample and precision/recall limitations. It switched from latest to hot, expanded the formula, loaded all 56 hot cards, and navigated to `e_6bc085af8fe5532a42a5c687`. That event displayed 34.8 / 100 with activity 5, publisher diversity 10 and recency 19.8, and preserved the original synthetic URL. The observed browser warning/error log was empty at the detail check.

Measured 80-article HTTP timings: snapshot 66.74 ms in the recorded attempt, events 33.65 ms, trends 39.06 ms; three repeated snapshot requests measured 32.71, 32.60 and 32.77 ms. These are bounded fixture measurements, not a formal production/performance baseline.

The temporary harness's raw deep-link fallback is defective: it catches FastAPI's exception subclass rather than the base exception raised by StaticFiles. It was not silently repaired in this round. Frontend root HTTP 200 and client-side navigation passed, and browser detail refresh passed after initial site load. That must not be reported as successful bare-server fallback or deployed Pages acceptance.

### Version and fixture provenance

The existing runtime configuration still produced `0.2.0` despite the new default. No environment file was edited. The isolated acceptance process explicitly used `APP_VERSION=0.5.0-alpha.1`.

A real controlled version transition changed generation from `39daf05f976049f06aaa2bd6` to `d79967863f5986d8f068f019`; all 80 article/event IDs remained unchanged, and the previous generation's events asset remained HTTP 200. Legacy generation-format reading is additionally covered by a unit test; no hosted production upgrade is inferred.

The initial synthetic batch completion marker preceded article insertion timestamps, so the first HTTP request correctly failed closed with 503. A fixture-only completion-marker transaction corrected that input state. Its post-commit evidence helper hit SQLAlchemy `MissingGreenlet` while reading an expired attribute; the transaction had already committed. Subsequent bounded-fixture evidence records the actual marker. These were test setup/logging issues, not product or production fixes.

Evidence files: `recovery-exit-codes.json`, `capacity-timeout.json`, `bounded-fixture.json`, `api-bounded-smoke.json`, `browser-smoke.json`, `version-migration.json`, `owned-final-stop.json`, and the updated `final-gates.json`.

All three owned acceptance processes are stopped: the overloaded capacity process was identity-checked and terminated; the two bounded/version processes stopped through their owned endpoint and exited zero. The temporary browser tab was closed. Existing user services and tabs remain untouched.

### Next sequential actions

- Await the user's decision on the disclosed capacity defect; profile the native matcher/projection using the preserved synthetic fixture.
- Make a semantics-preserving performance repair without resetting IDs, aliases or AI labels. If matching semantics change, require a new version-bound AI evaluation decision.
- Repair the temporary acceptance harness fallback and repeat fresh-client raw deep-link acceptance separately from service-worker-assisted refresh.
- Rerun backend/capacity/browser gates before marking M3 accepted or advancing M4 implementation.
- Retain seven-day production freshness, deployed candidate smoke, actual old-PWA-client upgrade and real-device acceptance. Do not tag or publish V1.0.0 on the basis of these local results.

## 2026-10-01 15:45Z 容量修复回归补充

本节优先于此前容量超时与路由失败状态。缓存键及隔离验收服务已修正；后端121、前端123、快照60共304项常规测试、类型检查、两模式构建与/News/ PWA路径通过。独立原生API 2,001篇数据库夹具按上限返回2,000篇、1,962事件；冷请求29.18秒未再触发45秒超时，版本资产及原始SPA深链200，全量趋势前后端一致。受控服务重启保留全部文章/事件ID、别名和代号；临时服务与标签页已关闭。

完整容量脚本尚未通过：它错误要求2,000篇必须生成2,000个事件，修正断言已询问用户，暂未执行；dense-2000分支未运行。保持M3-preview，不声明M3全量验收或V1发布。冷前端、生产SLA、旧PWA缓存、真实设备和七日生产门禁仍开放。本轮未Git提交/推送/发布。最新完整证据见 [V1_M3_CAPACITY_RECOVERY.md](V1_M3_CAPACITY_RECOVERY.md)。

## 2026-10-02 当前候选与 M5 执行入口

当前版本为 `0.9.0-alpha.1`，非正式 V1.0.0。用户已接受 M2 版本绑定的 AI 评估出口；M3 完整 2,000 篇通用/密集容量回归通过，M4 采用无已确认免费额度的关闭路径。
319 项候选测试、类型检查、snapshot/API 构建及 /News/ PWA 路径通过。原生实测使用隔离合成数据库，不代表已托管公网 API。
新增独立 HTTP 观测工作流 observe-news.yml 和原代码+原数据的 restore-pages.yml；记录不改写采集时间、不以 Actions 成功充当新鲜度、不用重新采集冒充回滚。
七天观测绑定 0.9 候选，真实跨度至少 168 小时，336 个闭合半小时窗口、至少 95% 有效且数据年龄不超过两小时，缺测和失败均计入分母。
允许先部署非正式候选开始观测；真实配对回滚/前滚、设备/PWA 升级、性能和七天证据必须另行关闭，未满足不得打 V1.0.0 标签。
最新完整证据与顺序见 [V1_M5_CANDIDATE.md](V1_M5_CANDIDATE.md)；AI 关闭边界见 [V1_M4_AI_DISABLED.md](V1_M4_AI_DISABLED.md)。此前文档中的未修复前缀、M2 等待人工、M3 未开始/容量断言待修正均为历史状态。
