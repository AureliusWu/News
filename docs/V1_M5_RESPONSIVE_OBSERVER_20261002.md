# M5 窄屏、错误恢复与云端独立观测续验

日期：2026-10-02；线上候选 `0.9.0-alpha.1` / `4978a84`。
本轮继续取得实际证据，但 **V1.0.0 NOT RELEASED**；上一轮新增验收工具的修正确认仍未收到答复。

## 当前状态核对

发布运行 `36954447724` 仍为成功，main 发布工作流处于 active。
只存在已知的本地验收文档变更及未纳入提交的 `frontend/tsconfig.node.tsbuildinfo`，没有清理其他工作。
上一轮标签页的句柄已不在本浏览器会话，实际标签列表为空；因此新建临时标签页，而不是因观察超时重复启动相同测试。

## 响应式实测

在同一个内置浏览器使用 390 x 844 视口覆盖；这是桌面响应式模拟，不是手机、触屏、移动浏览器或已安装 PWA 的验收。
垂直滚动条占据 15 px，实际文档可用宽度为 375 px。

- 首页显示 30 篇报道，版本 `V0.9.0-alpha.1`；导航、事件/收藏/来源入口、字号、筛选及新闻卡片均可见。
- 首页文档及 body 的 clientWidth/scrollWidth 均为 375，没有页面级横向溢出。分类条自身的横向滚动是既有设计，不称作页面溢出。
- 来源页显示采集时间 `2026/10/02 GMT+8 10:11:39`，正常 32/38，说明其不是实时检测或媒体可信度评分。
- “仅看异常”后恰有六个来源，页面 clientWidth/scrollWidth 同为 375。
- DW World、Nature News、DW German 为无近期合规条目；CBC World 为 ReadTimeout；RNZ World 为上游 403；China Daily China 为上游 404。原文日期缺失仍显示“未知”，未伪造时间，未把无合规条目等同于网站不可用。

证据：`artifacts/v1-m5-candidate-20261001/public-mobile-home-390.jpg`、`public-mobile-home-390-layout.json`、`public-mobile-sources.txt`、`public-mobile-abnormal-sources.txt`。

## 受控错误与恢复

在公网临时页直接请求不存在的合成事件 ID `e_000000000000000000000000`。
界面明确提示“当前快照中没有该事件的近期报道。事件链接可能已超出数据保留期。”，保留返回事件列表链接，没有白屏或虚构详情。
点击返回事件列表后重新显示 779 个事件，版本和快照时间保留。
证据：`public-missing-event.txt`、`public-missing-event-recovery.txt`。
最后已恢复默认视口并关闭本轮新建的临时标签页；没有关闭用户其他页面或清空缓存。
这只是读路径的不存在事件恢复，**不是完整采集失败、原生 worker 故障、公网原包回滚/前滚的替代证据**。

## 云端独立观测的真实运行和历史保留

两次手动触发既有 `observe-news.yml`，未改源代码、未部署新版本或引入付费服务。

| 运行 | 真实观测时刻 UTC | 工作流结果 |
| --- | --- | --- |
| [36956301885](https://github.com/AureliusWu/News/actions/runs/36956301885) | 2026-10-02T02:35:10.672Z | success |
| [36956596732](https://github.com/AureliusWu/News/actions/runs/36956596732) | 2026-10-02T02:39:05.125Z | success |

从第二次云端 `news-independent-observations` artifact 下载 history.json/report.json。
第二次历史包含两条观测；逐字段严格核对第一次记录与第一次下载输出一致，UTC 时刻、HTTP 状态、生成时间、候选源提交以及 `same_generation: false` 均未改写。
窗口计数核对闭合半小时桶，不把同窗口的两次手动运行算成两个合格窗口；既有错误记录没有因重跑被删除或覆盖。
实际保留证据：`observer-history-persistence.json`、`observer-first-cloud/`、`observer-second-cloud/`。

## 门禁结果与边界

第二份报告在 `2026-10-02T02:39:07.161Z` 评估：

- expected_version：`0.9.0-alpha.1`，candidate_version_bound 为 true；正式发布标志为 false。
- 窗口截止 `02:30Z`；两条新观测均仍处于当前未闭合窗口，因此 observed_slots/passing_slots/failed_slots 都为 0，missing_slots 为 336。
- 真实观测跨度 `0.06512583333333333` 小时，不是 168 小时。
- status：`WARMING_UP`；`gate_pass: false`；passing_fraction 为 0。
- 上一轮健康报告字段映射错误仍存在，两个原始失败判定照实保留。没有用正常 HTTP 或绿色工作流偷偷改写该判定。

已证明云端手动观测可执行、历史可跨运行恢复且不会因重跑清空；未证明定时任务实际间隔、数据发布代码复用、健康报告工具正确性或七天 95% 新鲜度。

## 后续仍需

1. 用户确认后修正新增恢复/观测工具字段及公网校验文件名，补当前 schema 正反回归；不得改变新闻采集时间或删除失败记录。
2. 实际完成旧原包回滚及候选原包前滚，并核对线上字节与原生成时间；演练后恢复正常发布调度。
3. 完成真实 168 小时、336 个闭合窗口、至少 95% 的候选新鲜度，以及真实的定时数据代码复用证据。
4. 完成真实手机、Firefox、其他旧/安装版 PWA 客户端与首屏/交互性能；响应式截图不能关闭这些门禁。

本轮没有新代码修正、后续提交或推送，最新验收文档仅保存在本地。

最终 V1 发布门禁结论：**FAIL**。
