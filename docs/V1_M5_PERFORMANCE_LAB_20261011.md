# M5 性能实验室补证与 Cloudflare 暂缓记录

日期：2026-10-11。用户决定暂时跳过 Cloudflare 部署，继续其他工作。

当前仍为 `0.9.0-alpha.1` / `M5-candidate`，`formal_release=false`。Cloudflare 状态为 **DEFERRED_BY_USER**，不是已部署、取消需求或豁免七天门禁。

## 本轮实际执行

- 对公开首页 `https://aureliuswu.github.io/News/` 执行桌面、移动模拟各三次 Lighthouse 冷导航审计。
- 固定 `lighthouse@13.5.0`，Apache-2.0；运行 Node.js `v24.14.0`，满足工具要求的 `>=22.19`。
- 使用已有 Chrome 的独立 headless 测试配置，不复用登录会话，不操作 Cloudflare 控制台、权限、Token 或计费。
- 默认 Lighthouse 模拟节流；桌面使用 `--preset=desktop`，移动使用默认配置。保留全部六个原始报告，没有择优、删慢样本或为提高分数修改配置。
- 读取最新独立云端观测报告，并单独实测公开新闻、来源健康和 release 元数据。
- 未修改应用、依赖清单、锁文件、采集器、部署工作流或发布门槛。未重新运行没有代码变化的完整后端/前端测试与构建；历史结果不冒充本轮结果。

## 六个原始性能样本

| 配置 | 样本 | Performance / 100 | LCP / ms | 三秒 LCP 代理比较 |
| --- | --- | --- | --- | --- |
| desktop | 1 | 98 | 779.464 | 达标 |
| desktop | 2 | 60 | 4359.797 | 未达标 |
| desktop | 3 | 100 | 581.283 | 达标 |
| mobile simulation | 1 | 97 | 2192.678 | 达标 |
| mobile simulation | 2 | 98 | 2183.332 | 达标 |
| mobile simulation | 3 | 94 | 2396.742 | 达标 |

六次工具退出码均为 `0`，没有 `runtimeError`。桌面 LCP 中位数 **779.464 ms**，范围 **581.283-4359.797 ms**；移动模拟中位数 **2192.678 ms**，范围 **2183.332-2396.742 ms**。

“三秒”这里只用于首屏目标的 LCP 代理比较，不把 Lighthouse 分数或 LCP 自动替换为完整产品验收定义。桌面三个样本未全部达标，不能仅用中位数宣称稳定通过。移动模拟三个样本达标也不代表真实手机、慢网现场、点击到结果的交互性能、API 冷启动或安装后 PWA 通过。

### 慢样本诊断

`desktop-2.json` 于 `2026-10-11T03:31:47.685Z` 开始审计，FCP `2549.884 ms`、LCP `4359.797 ms`、TBT `44.5 ms`、CLS `0`。

LCP 元素为实际新闻卡片的 `p.news-summary`，并非只看到空页面标题。报告提出图片交付约 **938 KiB** 的潜在节省，另有渲染阻塞、网络依赖树和缓存提示。它也记录了首页域名根路径 `favicon.ico` 的 `404`。

这些是诊断线索，不是已经证明的唯一根因。本轮没有改写第三方图片 URL、引入图片代理或依赖，也没有凭单次诊断修改应用。Lighthouse 模拟指标与诊断中的分项时间不能混用相加。后续优先检查缩略图请求、首屏请求依赖及 favicon 路径，再做同配置前后对照。

## 公网单点实测

观测时间：`2026-10-11T03:35:36.731Z`，即北京时间 `11:35:36`。

| 资源 | HTTP | 响应体原始字节 |
| --- | --- | --- |
| `/News/data/news.json` | 200 | 793147 |
| `/News/data/source-health.json` | 200 | 14575 |
| `/News/release.json` | 200 | 947 |

- 新闻数 `780`，快照生成于 `2026-10-11T02:14:13.805069Z`，本次年龄约 **1.357 小时**。
- 快照 ID `eafeab93abfe0cc565d3b20f`；`source-health.snapshot_id` 相同，`checked_at` 与新闻 `generated_at` 相同。已有 `isSnapshotPair` 实际返回 `true`。
- 来源 `32/38` 健康、`6` 失败，`22` 个发布者、`9` 个地区、`4` 种语言；采集门禁返回 `true`。来源失败没有被隐藏。
- 公开应用版本为 `0.9.0-alpha.1`，来源提交为 `1592e7919f9c132d891a9bd0fae87a8c9569baec`，应用构建时间 `2026-10-03T04:32:11.547Z`，正式发布标记为 `false`。
- 本轮开始时本地与远端文档 HEAD 均为 `2ce6e7fff98e489fc42136b0ecffa67a6eb33d31`；它不同于被复用的应用包提交，不把文档提交当作线上应用来源。

本地初次自动汇总 `artifacts/v1-m5-performance-20261011/summary.json` 的 `application_revision` 实际填入了上述文档 HEAD，命名不准确。该文件原样保留，但未作为本报告的线上应用版本证据，也未归入提交的证据目录；版本判断使用独立的公开 `release.json` 原始观测。

这是 Pages 静态快照的单点可访问与配对实测，不是已托管后端 API、完整七天记录或正式生产 SLA 通过。

## 最新七天云端报告仍为 FAIL

原始工作流：[独立观测 38104232879](https://github.com/AureliusWu/News/actions/runs/38104232879)，`schedule`，完成成功，来源提交 `2ce6e7fff98e489fc42136b0ecffa67a6eb33d31`。

评估时间 `2026-10-11T02:09:43.82Z`；窗口 `2026-10-04T02:00:00Z` 至 `2026-10-11T02:00:00Z`。

| 字段 | 原始结果 |
| --- | --- |
| expected_slots | 336 |
| observed_slots | 30 |
| passing_slots | 0 |
| failed_slots | 30 |
| missing_slots | 306 |
| passing_fraction | 0 |
| observation_span_hours | 189.49458555555555 |
| required_fraction | 0.95 |
| candidate_version_bound | true |
| status / gate_pass | FAIL / false |

下载的原始历史包含 `38` 条观测。最近三条观测的页面/新闻均为 `200`，版本、采集门禁及数据配对正常，但数据年龄分别约为 `4.13`、`3.40`、`2.56` 小时，超过两小时要求。实际调度存在缺测和过期，不能靠等待或把 Actions 绿色运行当作验收通过。

[最新发布 38104463232](https://github.com/AureliusWu/News/actions/runs/38104463232) 于 `2026-10-11T02:13:43Z` 开始并成功完成；之后的新鲜单点不抹掉此前失败窗口。

本轮直接引用该工作流产生的原始 `report.json`，没有合并、重命名或重新计算此前命名错误的输入，也不称其为“全部已知本地与云端记录的最终合并”。此前观测输入命名修正仍待明确确认。归档文件名只是证据归档，不作为时间戳匹配的门禁输入。

## 可复现命令

在项目根目录运行，生成新的输出目录，保留失败输出；不要覆盖本轮原始报告。

```powershell
$env:CHROME_PATH = 'C:\Program Files\Google\Chrome\Application\chrome.exe'
$out = 'artifacts/v1-m5-performance-next'
New-Item -ItemType Directory -Path $out -Force | Out-Null
foreach ($mode in @('desktop', 'mobile')) {
    foreach ($sample in 1..3) {
        $args = @('exec', '--yes', '--package=lighthouse@13.5.0', '--',
            'lighthouse', 'https://aureliuswu.github.io/News/',
            '--only-categories=performance', '--chrome-flags=--headless=new',
            '--output=json', "--output-path=$out/$mode-$sample.json", '--quiet')
        if ($mode -eq 'desktop') { $args += '--preset=desktop' }
        & npm.cmd @args
        "mode=$mode sample=$sample exit=$LASTEXITCODE"
    }
}
```

新测试如要比较改动效果，需保持工具版本、机器、配置、URL 和样本数一致；所有失败与慢样本一并计入。官方说明：[Lighthouse CLI](https://github.com/GoogleChrome/lighthouse#using-the-node-cli)、[分数波动与指标解释](https://developer.chrome.com/docs/lighthouse/performance/performance-scoring)。

## 证据与下一顺序

证据目录：`docs/evidence/v1-m5-performance-20261011/`，包含六个 Lighthouse 原始 JSON、`public-after.json`、原始云端七天报告/历史及工作流运行记录。完整终端日志保留在本地 `artifacts/v1-m5-performance-20261011/`。

1. 先检查已有首屏请求/图片与 favicon 问题，按固定配置做改动前后性能对照，保留本轮慢样本。
2. 完成真实手机、Firefox、旧客户端 PWA 升级和真实断网验收；模拟设备和静态 PWA 文件检查不替代这些证据。
3. Cloudflare 部署暂缓；未启用替代平台、个人电脑定时器、收费服务或新增凭据。可靠调度和合格七天新鲜度门禁继续开放。
4. 经确认后修正此前观测输入命名，完整保留失败历史并重算全部已知观测。
5. 全部门槛真实关闭后才能创建 V1.0.0 正式标签和发布；本轮不创建、不冒充完成。
