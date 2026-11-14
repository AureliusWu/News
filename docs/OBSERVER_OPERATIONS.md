# 独立新闻观察器操作

在 Actions 中选择 Independent News Freshness Observer，使用 Run workflow：

- `continuous=false`（默认）：一次取样，适合人工检查；所有 schedule 运行也始终单次取样。
- `continuous=true`：仅本次手动运行执行 11 次取样，目标间隔 30 分钟，约覆盖五小时；不是新建定时任务。
- `expected_version` 与 `expected_revision`：保持与实际受评应用绑定，revision 必须为完整源码 SHA。留空时使用既有 pinned repository variables/工作流默认值，不得用新版本参数承认旧样本。

旧 repository variable `NEWS_OBSERVER_CONTINUOUS` 不再激活连续模式；无需为了开启/关闭连续观察而修改它。脚本仍读取同名环境变量，但该值由 workflow 的事件类型和 continuous 输入派生，schedule 固定 false。

观察器不会因连续取样自动开启恢复。`NEWS_AUTO_RECOVERY_ENABLED`、`NEWS_RECOVERY_REF` 仍为独立控制，原固定标签核验、单次上限与发布冲突检查保持。历史 Artifact 恢复失败不能以空历史替代；真实取样、数据绑定、七天覆盖率和任务是否成功分别判断。绿色任务不代表七天门禁通过，也不代表所有新闻源健康。

本次仅更新运行说明、架构说明和 README 目录切换；没有发布新应用或更改已批准源码。验证：对照现行 workflow/watch-public.mjs，并执行 release-gates 与 observation-recovery 的无网络合同测试。
