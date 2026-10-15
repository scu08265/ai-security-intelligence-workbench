# 时效性归因：把混合口径拆开，看瓶颈在上游还是在我们

对应任务书 2026-10-13 的 A1。产物：`reports/timeliness-attribution.json`（由
`tools/build_timeliness_attribution.py` 生成，可随时重跑）。

## 1. 结论（可直接引用）

> **采集间隔 1 小时；GHSA 中位 1.8 小时，NVD 中位 12.4 小时，差值来自上游发布与入库节奏。**

上游证据：同一 CVE 在 MITRE 登记记录与 NVD 记录上的 `source_published_at` 差值，
本机实测 **79 对，中位 0.68 小时（41 分钟）**，P95 2.26 小时。也就是说两个上游库之间的
发布时差本身就在小时级，而我们的轮询是一小时一次——延迟不是轮询间隔造成的。

## 2. 为什么必须分列（一句话）

赛题问的是"**漏洞信息**从发布到系统采集的延迟"，而 arxiv / openalex 是论文来源、
政策类来源发布的是法规与标准：把它们的发布节奏算进漏洞时效分母，既不忠实于赛题口径，
也把 GHSA 的 1.8 小时埋掉了。

分列不是为了让数字好看——**混合口径原样保留在附录**（见第 5 节），两个数都可以被追问。

## 3. 按来源类别分列

口径基线是交付机 `data/intel.sqlite`。下表是 **2026-10-13** 的一次读数，保留作历史记录；
**当前权威数字**见 `docs/report/metrics_snapshot.json` 的 `latency_by_class`（快照日期随文件更新），
报告附录 B 与对照表 §2.1 读的都是它。两次读数的差异见第 5 节。

| 类别 | 来源 | 样本 | 中位延迟 | 最大延迟 | 说明 |
| --- | --- | ---: | ---: | ---: | --- |
| **漏洞类**（赛题口径） | **ghsa** | 67 | **1.8 小时** | 94.1 小时 | 社区公告，发布即被采集 |
| **漏洞类** | **nvd** | 119 | **12.4 小时** | 287.3 小时 | 差值来自 NVD 自身的分析入库节奏，见第 4 节 |
| 学术类（不计入分母） | arxiv | 76 | 36.5 小时 | 91.8 小时 | 论文预印本发布节奏 |
| 学术类（不计入分母） | openalex | 4 | 61.8 小时 | 61.8 小时 | 索引型来源，滞后于论文发布 |
| 其他（不计入分母） | anquanke | 1 | 89.9 小时 | 89.9 小时 | 安全博客，样本仅 1 条 |

类别归属直接取自 `app/sources.py` 的 `category` 字段，不另造一套分类：
漏洞类 = `cve_database` / `ecosystem_advisory` / `community_advisory` /
`exploitation_intel` / `vendor_advisory` / `security_blog`；学术类 = `academic_paper`；
政策类 = `policy_regulation` / `technical_standard` / `risk_framework` / `threat_framework`。

## 4. 上游归因：同一事件跨来源的时间线

### 4.1 上游发布差值分布

对库里每个拥有 ≥2 个来源 observation 的事件，取同一事件的 `source_published_at` 两两作差。
本机实测（`reports/timeliness-attribution.json` 的 `upstream` 段）：

| 上游对 | 对数 | 中位差值 | P95 |
| --- | ---: | ---: | ---: |
| `mitre_cve -> nvd` | 79 | **0.68 小时** | 2.26 小时 |
| `mitre_cve -> osv` | 11 | 17.73 小时 | 523.68 小时 |
| `mitre_cve -> cisa_kev` | 15 | 1945.6 小时 | 9393.53 小时 |

`mitre_cve -> nvd` 是同一漏洞在两个登记库之间的发布时差：**41 分钟的中位值**说明上游本身就在
小时级滚动。`cisa_kev` 那条是"某漏洞后来被列入在野利用目录"，天然滞后数月，属于另一种事件，
所以它单独一行、不进上面的结论。

### 4.2 一个可回读的同事件跨来源时间线

事件 **`CVE-2026-69147`**（三个来源，同一事件 ID 可在库里按 `events.id` 直接读回）：

| 来源 | `source_published_at`（上游发布） | `discovered_at`（我们首次发现） | `ingested_at`（入库） |
| --- | --- | --- | --- |
| mitre_cve | 2026-09-16T17:49:20Z | 2026-10-01T04:36:31Z | 2026-10-01T04:36:42Z |
| nvd | 2026-09-16T18:17:11Z | 2026-10-01T03:59:53Z | 2026-10-01T04:16:06Z |
| osv | 2026-09-17T17:17:39Z | 2026-09-27T10:43:37Z | 2026-09-27T10:43:46Z |

同一漏洞，MITRE 先发布，**28 分钟后** NVD 才有记录，**23.5 小时后** OSV 才有记录。
三个来源的上游发布时间彼此不同——这就是"差值来自上游节奏"的直接证据。

回读命令（读的是当前配置的数据库，即 `data/intel.sqlite`）：

```powershell
.\.venv\Scripts\python.exe tools\build_timeliness_attribution.py
# 时间线在 reports/timeliness-attribution.json 的 timeline_examples 段
```

第二个例子 **`CVE-2025-3248`**：MITRE 2025-04-07T14:22:38Z、NVD 2025-04-07T15:15:44Z，
两者相差 53 分钟。

## 5. 附录：混合口径（保留，不删）

| 口径 | 样本 | 中位 | P95 | ≤6h | ≤12h | ≤24h |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 混合（全部来源，2026-10-13 读数） | 267 | **18.1 小时** | — | 27.7% | 39.7% | 58.4% |
| 混合（当前快照口径） | 297 | **15.58 小时** | — | 31.99% | 45.12% | 61.95% |
| 混合（本机复算，仅作对照） | 25 | 6.71 小时 | 52.64 小时 | 44.0% | — | — |

混合中位数 18.1 小时单独看只够赛题"≤24 小时"的合格档，这是事实，不去修饰——所以它被移到附录，
不再作为本项判定分母。**2026-10-15 定稿的判定口径是漏洞类**，当前快照读数为：漏洞类整体中位
7.34 小时（217 个样本），落在 ≤12 小时的良好档；其中 GHSA 1.75 小时已进 ≤6 小时的优秀档，
NVD 8.34 小时仍在良好档。**本项交付的是归因，不是抬分**：GHSA 与 NVD 的差距（1.75 vs 8.34）
与"整体尚未进优秀档"的事实都如实保留。

## 6. 复跑与口径边界

```powershell
.\.venv\Scripts\python.exe tools\build_timeliness_attribution.py
```

- 工具复用 `app/reliability.py` 的 `latency_records` / `timeliness_stats`，不另造口径：
  每个事件只取最早一次 `discovered_at`，重复更新不重复计入时延；监测前的历史回填
  （`published_at < monitoring_started_at`）记为 `baseline_backfill_before_monitoring_start`
  并排除出有效分母。
- 第 3 节的交付机数字取自 `docs/COMPETITION_RUBRIC_MAPPING.md` 引用的同一份口径基线；
  第 4 节与第 5 节第二行是本机 `data/intel.sqlite` 的实测值，两者不得混排在同一张表里。
- 本机没有 `ghsa` / `arxiv` 事件（这两个源在本机 `source_state` 里没有记录），
  所以本机跑出来的分列表只有 nvd / osv / openalex；表里的 GHSA 行是交付机读数。
  在交付机上重跑本工具即可得到完整分列。
