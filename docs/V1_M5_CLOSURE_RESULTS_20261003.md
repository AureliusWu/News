# M5 本轮实测结果（自动整理）

日期：2026-10-03（Asia/Shanghai）。当前公开应用仍为 0.9.0-alpha.1，正式 V1.0.0 未发布。

## 已完成

- 用户确认后审阅并快进同步远端 README 提交 3cd4389，保留本地未跟踪的 TypeScript 构建信息。
- 验收契约修正提交：1592e7919f9c132d891a9bd0fae87a8c9569baec，已推送。
- 本轮测试：后端 121、快照 60、前端 123、Node 门禁 17、Pages 恢复 16，共 337 项通过。
- 前端类型检查通过；snapshot/API 两种构建及 /News/ PWA 构建规则检查通过；提交前 git diff --check 通过。
- [候选部署](https://github.com/AureliusWu/News/actions/runs/37096825016) 成功。
- [旧版公开回滚](https://github.com/AureliusWu/News/actions/runs/37096984828) 成功，公网全部 18 个原始文件 HTTP 200 且 SHA-256 完全一致。原新闻生成时间 10/01/2026 23:26:49，791 篇；未重新采集或改写时间。
- [候选公开前滚](https://github.com/AureliusWu/News/actions/runs/37097126960) 成功，公网全部 34 个文件 HTTP 200 且 SHA-256 完全一致。版本 0.9.0-alpha.1，源码 1592e7919f9c132d891a9bd0fae87a8c9569baec，生成时间 10/03/2026 04:31:57，796 篇。
- 已实测读取 PAGES_DEPLOY_ENABLED=true，定时发布恢复。前滚与回滚均恢复原始应用和原始成对数据，不把单次命令成功当成公网证明。
- [修正后独立云端观测](https://github.com/AureliusWu/News/actions/runs/37097286700) 的实际采样时间为 2026-10-03T04:40:00.481Z，报告绑定为 true。全量原始 JSON 人工逐条对照：原有六条记录保留，第七条为新观测，未抹去历史失败。
- [旧版冻结技术备份](https://github.com/AureliusWu/News/releases/tag/news-pages-rollback-v0.2-20261001) 已建立并从 GitHub 下载恢复验证；新 ZIP SHA-256 为 025a69bf916dcfbdc0bd7cfd8dae28e15b6065699d0196f85e0ad84422ff2e7b。它是原文件重新封装的技术备份预发布，不是 V1.0 正式版本。原包与新容器的哈希、源 run 和逐文件 pin 均保留。
- Pages 发布、恢复包及 source-health 证据保留期延长至八天；冻结备份不再依赖原 Actions 包一天的有效期。

## 仍未通过的门禁

独立报告评估时间：10/03/2026 04:40:02。状态 WARMING_UP，gate_pass=false，真实跨度 26.0805025 小时，要求 168 小时。已闭合 336 个半小时时段中，观测 5、通过 0、失败 5、缺失 331，通过比例 0，要求至少 0.95。修正后的最新点尚在开放时段，不能把它提前算作闭合时段。

- 部署前一次真实快照年龄为 2.504 小时，已经超出两小时要求；近七天实际计划发布 34 次，最大相邻间隔 8.325 小时。这些是调度稳定性风险，不能仅等待七天或手动补造记录后宣称通过。
- 真实 Android/iOS、Firefox、已安装 PWA 更新/离线以及原性能要求仍无完整证据。
- 本轮 Chrome/Edge 连接报错，内置浏览器两次操作超时且重置内核；只确认了 HTTP/原包字节及云端观测，不能声称本轮浏览器渲染通过。打开页面请求仅返回 queued，也不是已显示证据。
- 未建立新的收费服务、新闻内容 AI 调用或额外公网常驻 API。

## 保留的错误和告警

- 第一次快照测试误用未安装 feedparser 的后端环境而失败；使用独立环境安装仓库已有锁定 requirements 后，全部 60 项通过。原失败日志未覆盖。
- 后端 121 项通过并退出 0，但出现 3097 条 Python 3.14 弃用告警及 pytest 临时目录清理 WinError 5；不能声称零告警。
- 本地临时历史断言把 JSON 根对象误当成数组，失败后没有修正或计为 PASS。真实结构是 schema_version + observations；原始前后数据已完整查看并逐条对照。生产观测工具的 17 项 Node 测试和云端观测与该一次性断言不同。
- 两处新增文档末尾空行曾使格式检查失败；规范化末尾换行后格式检查通过。

## 证据路径与下一步

原始文件在 artifacts/v1-m5-closure-20261003/：测试日志、public-rollback.json、public-forward.json、原始冻结 receipt、云端恢复 receipt、observer-before/history.json、observer-after/history.json 和 report.json。来源和边界说明见 [验收工具修正](V1_M5_TOOL_CORRECTION_20261003.md)。

下一步必须先解决真实漏发布/漏观测的调度稳定性，再累积合格的实际七天覆盖，并完成真实设备、跨浏览器、PWA 和性能验收。未关闭这些门禁前，不升级为 1.0.0、不创建正式版本标签、不发布虚假的完整验收结论。
