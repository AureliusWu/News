# 2026-11-01 RSS 来源修复与复验

## 问题和修复

DW 英语、DW 德语、Nature 的 RSS 1.0 feed 使用 dc:date，feedparser 将其放在 updated 字段；采集器要求原始 published，导致所有条目被拒绝。不能直接使用 updated、dc:date 或采集时钟冒充首发时间。

现增加配置驱动、默认关闭的原文元数据模式。仅三个配置源可在 RSS 缺失原始首发字段时读取同一篇官方文章的 JSON-LD datePublished，验证 HTTPS 同主机 / 标准端口、文章身份和 canonical。明确类型的主文章或精确 canonical 绑定的 WebPage.mainEntity 才能提供日期。没有跨域跟随、更新时间回退、日期补时区、缺日期补午夜或放宽时效阈值。Nature 自己明确提供的 datePublished 午夜值可按原值保留。

复用现有依赖，无新增生产依赖、数据库迁移或基础设施。每源最多 8 次原文查询，25 秒新查询启动预算；每次 I/O 最长 8 秒，沿用 4 MiB 上限。公开文章 ID、收集 URL、来源归属和原发布时间语义保持。新增诊断字段只记录有界数量和安全原因代码。

## 实测结果

初次定向采集中，DW 英语 / 德语各接受 7 条，Nature 接受 8 条；RNZ 在本次已自行恢复响应。之后全量采集发生网络和上游变化，因此以以下最终全量结果为准，不能将前一轮成功拼成后一次的全源通过。

最终采集时间（UTC）：2026-11-01T03:31:33.321680Z。38 源中 33 健康、5 失败，724 篇，22 家发布者、9 个地区、5 种语言，原采集发布门禁通过。运行前后采集器、注册表和配置的 SHA-256 一致，完整原始来源报告、代码指纹与范围见 [机器证据](evidence/SOURCE-REPAIR-20261101.json)。这是本地 HTTP 采集，不是已部署或实体设备验收。

| 来源 | 最终状态 | 有效条目 | 说明 |
| --- | --- | ---: | --- |
| dw-world | PASS | 7 | 原始首发时间有效 |
| cbc-world | FAIL | 0 | Feed has no parseable entries |
| rnz-world | PASS | 1 | 原始首发时间有效 |
| nature | FAIL | 0 | No valid articles with original publication dates within seven days |
| china-daily | FAIL | 0 | Upstream HTTP 404 |
| scmp-china | FAIL | 0 | Upstream HTTP 403 |
| dw-german | PASS | 7 | 原始首发时间有效 |
| nyt-world | FAIL | 0 | Feed has no parseable entries |

Nature 最终原文查询被跨主机重定向或超时拦截，仍保留失败；CBC 返回不可用 HTML，中国日报旧 feed 为 404。SCMP 与 NYT 在最终采样中也出现上游失败。没有禁用这些源、换名为其他发布者或删掉失败记录。本轮不声称 38/38 或七天门槛通过。

## 验证

- Python 3.12：快照全套 83 项通过，包含新增 17 项首发元数据 / 来源请求回归。
- 后端全套 126 项通过，1 项现有 AnyIO / Starlette 弃用警告；注册表拒绝未知模式、RSSHub 和非标准 HTTPS origin。
- 发布 / 观察相关 Node 测试 32 项通过；七天统计规则、原豁免及正式源绑定均保留。
- 两套环境分别安装仓库各自 requirements；没有为测试更改锁文件或生产依赖。新增 socksio 仅用于本地环境既有代理的测试兼容，不是项目依赖。
- git diff --check 通过。没有重跑前端或真机验收；本轮未修改前端程序。

## 部署边界

维护提交使用 [skip ci]，避免 main push 重建候选 UI 覆盖正式应用。应用 1.1.0、正式标签、批准记录和公开 Release 不变；既有计划刷新随后采用新采集器，并复用已验证正式应用包。本地报告 deployment=false，不把源码修复当作公开部署完成，不重标旧报告、补填缺测或移除未完成设备项。

## 参考

- [feedparser entries.published](https://feedparser.readthedocs.io/en/stable/reference-entry-published.html)
- [feedparser entries.updated](https://feedparser.readthedocs.io/en/stable/reference-entry-updated.html)
- 官方 feed：配置 config/sources.yaml 及上述机器证据中的 feed_url。
