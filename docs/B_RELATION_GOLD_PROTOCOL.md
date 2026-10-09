# B 关系抽取金标准协议与局限（2026-10-04 批次）

本文件说明 `evaluation/b_relation_gold_20261004.json` 是怎么做出来的、
FN 是怎么发现的、哪些数字不能引用，以及为什么这里的 Recall 只能叫
**抽样穷尽 Recall**。

## 1. 为什么需要这份金标准

`evaluation/b_relation_candidates_*.json` 是**系统自己的输出**。在它上面做人工标注，
只能回答"抽出来的对不对"（Precision），永远得不到"该抽而没抽"的样本，
因此 `relation_score_all.json` 里 Recall 与 F1 一直是 `null`。

本批次的做法是：**换一个起点** —— 不再从候选出发，而是**从源头出发**逐条枚举
"应抽取关系"，再回头找系统漏掉了哪些。这样 FN 才有来源。

## 2. 抽样范围（抽样穷尽，不是全语料穷尽）

| 类别 | 对象 |
|---|---|
| 论文 3 篇 | `paper:2609.28996`（DistillGuard）、`paper:2609.29757`（OllamaDrama）、`paper:2609.28900`（Codetta），以及 paper 字段指向它们的 OpenAlex 事件 |
| CVE 事件 3 个 | `CVE-2026-64849`、`CVE-2025-62593`、`CVE-2026-33017`（CISA KEV 采集，副本内有 NVD 快照） |
| 生态漏洞事件 2 个 | `PYSEC-2026-4000`、`GHSA-8pw2-6jv3-mj5j` |
| 官方/标准文档 3 个 | `official:eu_ai_act`、`source:nist_ai_rmf`、`source:owasp_genai`（六维度不覆盖文档间关系，预期 0 条，已核对） |

范围之外的关系**一条都没有写进 gold**，避免用不完整标注抬高 Recall。

## 3. 穷尽协议（源头是什么）

| 维度 | 全集依据 | 证据形式 |
|---|---|---|
| `cvss` | 事件 `cvss[]`；副本 NVD 快照 `metrics.cvssMetric*[]` | 事件字段路径 / NVD 文件路径 + `metrics.*` 定位 + baseScore/baseSeverity |
| `version_range` | 事件 `affected[].range` | `events[<id>].affected[i].range` + `source_id` |
| `fixed_version` | 事件 `affected[].fixed_version` | `events[<id>].affected[i].fixed_version` + `source_id` |
| `paper_link` | 事件 `paper.pdf_url` / `paper.arxiv_id` | `events[<id>].paper.*` |

枚举后按 `(维度, subject, object)` 归一化比对系统候选：

* 有匹配候选且人工标签 `positive` → 计入 gold（构成 TP）；
* 有匹配候选但标签 `unknown` → 进 `uncertain`，**不进任何分母**；
* 没有任何匹配候选 → **真实 FN**，分配新 id（`BREL-GOLD-FN-<维度>-NNNN`）并记录
  "为什么应抽取 / 系统为什么漏"。

> 特别注意：被标为 `unknown` 的候选**不能**写进 `expected_relation_ids`。
> 因为评分的 FN 逻辑是"expected 里没有出现在 human positive 中的就是 FN"，
> 一旦写进去，会被重复计数一次（既算未判定、又算漏检）。

## 4. 本批次发现的真实漏检（FN）

共 **5 条**，全部是 `cvss` 维度，来自同一条链路缺口：

| FN ID | subject | 向量（截断） | 来源 |
|---|---|---|---|
| `BREL-GOLD-FN-CV-0001` | CVE-2026-64849 | `CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:L/A:N` | 副本 NVD 快照 `metrics.cvssMetricV31[0]`（baseScore 9.3 / CRITICAL） |
| `BREL-GOLD-FN-CV-0002` | CVE-2025-62593 | `CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:P/...` | 同上（v4.0） |
| `BREL-GOLD-FN-CV-0003` | CVE-2025-62593 | `CVSS:3.1/AV:N/AC:L/PR:N/UI:R/S:U/C:H/I:H/A:H` | 同上（v3.1） |
| `BREL-GOLD-FN-CV-0004` | CVE-2026-33017 | `CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/...` | 同上（v4.0） |
| `BREL-GOLD-FN-CV-0005` | CVE-2026-33017 | `CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H` | 同上（v3.1） |

原因：这三条 CVE 由 **CISA KEV** 采集，KEV 目录不带 CVSS，事件里 `cvss[]` 为空；
而采集链路只把 NVD 的 *Exploit 引用*回填到 `poc[]`（`tools/backfill_nvd_poc.py`），
**没有合并 NVD 的 `metrics`**，因此 cvss 维度整片漏掉。证据与解释见
`artifacts/b_eval/relation_missed_relations_20261004.json`。

## 5. 两种评分口径（都必须看，不能混引）

| 文件 | 输入 | Precision 口径 | Recall 口径 | micro 结果 |
|---|---|---|---|---|
| `relation_score_gold_20261004.json`（队长指定命令） | 全量已标注 121 条 | **全量**已标注候选（TP 47 / FP 0） | **抽样**范围（FN 5） | P=1.0、R=0.9038、F1=0.9495 |
| `relation_score_gold_scope_20261004.json`（口径一致版） | 仅抽样范围内候选 | 抽样范围（TP 5 / FP 0） | 抽样范围（FN 5） | P=1.0、R=0.5、F1=0.6667 |

两份文件的分子分母都对得上（`precision = TP/(TP+FP)`、`recall = TP/(TP+FN)`、
`F1 = 2PR/(P+R)`），但**只有当输入与 gold 的范围一致时，P/R/F1 才是同一个口径**。
因此：

* 要引用"关系抽取的 Precision" → 用全量口径（47/47）；
* 要引用"抽样范围内的 Recall/F1" → 用**口径一致版**；
* **不要把两份额度不同的数字合起来当一个综合成绩**。

## 6. 为什么只能叫"抽样穷尽 Recall"

* 枚举只覆盖上面 11 个对象，不是全语料；
* 源头只用到"事件字段 + 副本里的 NVD 快照"；OSV 快照结构未解析成功、NVD 只覆盖
  已抓取的 37 个 CVE，官方文档不参与六维度关系；
* 因此这个 Recall 的含义是：**在抽样范围内、以可得源头为准的召回率**，
  不能外推成全语料召回率，也不能当成"系统整体 Recall"。

## 7. 不确定项

`gold.uncertain` 收录 7 条：它们在抽样范围内、系统已有候选，但人工标签为 `unknown`
（例如来源未提供区间字段）。这些条目**不计入任何分母**，
既不当作命中，也不当作漏检。评分输出里它们体现为对应维度的 `undetermined`。

在口径一致版里 `cvss` 的 Precision 是 `null`：范围内该维度的候选全部是待定，
而 5 条漏检是明确的 FN —— 也就是"有分母的召回、没有分母的精确"，如实呈现，不补数。

## 8. 与旧产物的关系

* `artifacts/b_eval/relation_score_all.json` 等旧冻结产物 **0 改动**（仍是
  `tp=47, fp=0, fn=0, recall=null, fn_source.available=false`）；
* 本批次新增的文件全部带 `_gold_20261004` / `gold_20261004` 后缀。

## 9. 复现命令

```powershell
# 1) 生成 gold 与 FN 清单（只读数据库/快照，只写新文件）
.\.venv\Scripts\python.exe tools\build_b_relation_gold.py

# 2) 队长指定命令：全量已标注输入 + 抽样 gold
.\.venv\Scripts\python.exe tools\score_b_relation_annotations.py `
  --input artifacts\b_eval\relation_candidates_labeled_all.json `
  --gold evaluation\b_relation_gold_20261004.json `
  --out artifacts\b_eval\relation_score_gold_20261004.json

# 3) 口径一致版：抽样范围内输入 + 同一 gold
.\.venv\Scripts\python.exe tools\score_b_relation_annotations.py `
  --input artifacts\b_eval\relation_candidates_labeled_gold_scope_20261004.json `
  --gold evaluation\b_relation_gold_20261004.json `
  --out artifacts\b_eval\relation_score_gold_scope_20261004.json
```

## 10. 下一步（不在本批次范围）

1. 补齐 NVD `metrics` 合并到 `cvss[]`（可复用 `tools/backfill_nvd_poc.py` 的思路），
   这 5 条 FN 就会转为 TP；
2. 解析 OSV 快照，把 `ranges[].events.fixed` 也纳入穷尽枚举，扩大 FN 搜索面；
3. 扩样（更多 CVE/论文/标准文档）后再谈"全语料 Recall"。

## 11. 2026-10-06 批次：NVD CVSS 漏检复核（5 条 FN 的收敛）

本节记录第 4 节那 5 条 `cvss` 漏检在根因修复后的复核结果。

### 11.1 根因与修复

根因见第 4 节：这三条 CVE 由 **CISA KEV** 采集，事件 `cvss[]` 为空，而采集链路
只把 NVD 的 Exploit 引用回填到 `poc[]`，**没有合并 NVD 的 `metrics`**。

修复 commit **`6d15d31`**（`fix: merge NVD CVSS metrics in the backfill so cvss
relations are extractable`）：
`tools/backfill_nvd_poc.py` 现在同时合并 `cvss`；`app/storage.py` 新增
`merge_event_cvss()`，按 `(source_id, vector)` 去重合并。说明见
`docs/NVD_CVSS_BACKFILL_FIX.md`。

### 11.2 本批次的复现路径（真实库副本，可回读）

1. 复制真实库 `D:\ICT\intel-data-b` 为副本（真实库 SHA256 `4095A5B1…254285` 全程未变）；
2. 对副本按 CVE 定向请求 **NVD CVE API 2.0**（`services.nvd.nist.gov`），
   取得 `CVE-2026-64849` / `CVE-2025-62593` / `CVE-2026-33017` 的原始响应，
   存为副本 `snapshots/nvd/<CVE>.json`（含 SHA256 清单：
   `artifacts/b_eval/relation_cvss_recheck_verification_20261006.json`）；
3. 用修复后的 `tools/backfill_nvd_poc.py` 回填副本：`cvss_events_updated=4`；
4. 重跑候选：`evaluation/b_relation_candidates_20261006.json`
   （四维候选由 121 增到 127，cvss 维度 22 → 28）；
5. 用 `tools/relabel_b_relation_candidates.py` 按**关系内容**（不是 id）把上一批次
   121 条人工标注迁移到新候选（121/121 命中），再对 5 条新 cvss 关系写入人工核验标注；
6. 用 `tools/verify_b_relation_cvss_recheck.py` 复核"旧 5 个合成 id ↔ 新 5 个候选 id"
   是否真的一一对应（主体 / 关系类型 / 对象 / 证据四项，逐条 11 项检查）；
7. 重跑 gold：`tools/build_b_relation_gold.py --former-missed
   artifacts/b_eval/relation_missed_relations_20261004.json ...`
   → `evaluation/b_relation_gold_20261006.json`（带 `resolved_former_ids` 映射）；
8. 评分两份：页面口径 `artifacts/b_eval/relation_score_gold_20261006.json`
   （gold 用 `_20261006`）、对照口径
   `artifacts/b_eval/relation_score_gold_frozen20261004_20261006.json`（gold 用 `_20261004`）。

### 11.3 人工核验结果（5/5）

逐条把库内 `cvss[].vector` 与第 4 节金标准期望向量**逐字符比对**，并确认该向量
逐字出现在 NVD 官方快照原文（可回读）：

| 原 gold id | 事件 | 新候选 id | 库内命中 | 快照可回读 |
|---|---|---|---|---|
| `BREL-GOLD-FN-CV-0001` | CVE-2026-64849 | `BREL-CV-0021` | ✅ | ✅ |
| `BREL-GOLD-FN-CV-0002` | CVE-2025-62593 | `BREL-CV-0022` | ✅ | ✅ |
| `BREL-GOLD-FN-CV-0003` | CVE-2025-62593 | `BREL-CV-0023` | ✅ | ✅ |
| `BREL-GOLD-FN-CV-0004` | CVE-2026-33017 | `BREL-CV-0024` | ✅ | ✅ |
| `BREL-GOLD-FN-CV-0005` | CVE-2026-33017 | `BREL-CV-0025` | ✅ | ✅ |

核验清单：`artifacts/b_eval/relation_cvss_recheck_verification_20261006.json`
（含 `resolved_former_ids`：旧合成 id → 新候选 id）；新增标注清单（署名
`人工复核-用户确认` / `2026-10-09`）：
`artifacts/b_eval/relation_new_positive_proposals_20261006.json`。
映射同时写进 gold 的 `resolved_former_ids`，并逐条记下对应候选的
`system_evidence_source_id`，便于反查。

### 11.4 分数变化

| 口径 | 输入 | gold | TP | FP | FN | P | R | F1 |
|---|---|---|---|---|---|---|---|---|
| 10-04 冻结基线 | 121 条 | `gold_20261004` | 47 | 0 | 5 | 1.0 | 0.9038 | 0.9495 |
| **本批次（页面口径，active）** | 标注 `_20261006` | `gold_20261006` | 52 | 0 | **0** | 1.0 | **1.0** | **1.0** |
| 本批次（对照口径） | 标注 `_20261006` | `gold_20261004` | 52 | 0 | **5** | 1.0 | **0.9123** | **0.9541** |

两份文件：页面口径 `relation_score_gold_20261006.json`、对照口径
`relation_score_gold_frozen20261004_20261006.json`（带 `frozen` 前缀，因此不会被
`app/b_evaluation.py::_active_relation()` 的正则选中）。两份都记录 `input_source` /
`gold_source`，不会看错来源。
`cvss` 维度：TP 10 → **15**，FN 5 → **0**。

### 11.5 为什么"任务指定命令"下 FN 仍为 5（必须如实说明）

`score_b_relation_annotations.py` 的 FN 判定是**按 `relation_id` 逐条比对**
（`missing_ids = expected_ids - 已验证 positive 的 id`）。
10-04 的 gold 冻结了 5 个**合成 id**（`BREL-GOLD-FN-CV-0001..0005`）作为"应抽取"全集；
修复后系统抽出的这 5 条关系拿到了**新 id**（`BREL-CV-0021..0025`），
旧 id 无从匹配，因此按字面命令评分时这 5 个旧 id 仍被计为 FN。

也就是说：**数据侧的漏检已经真实收敛（TP 由 47 增到 52，cvss FN 由 5 减到 0），
但"旧 gold 的 id 与修复后候选集的 id 不同源"这一表示层问题会让字面命令的 FN 不下降。**

要让 FN 指标也收敛到 0，需要把 gold 的 expected 改指向真实候选 id —— 即本批次
用**同一协议、同一抽样范围**重跑出的 `evaluation/b_relation_gold_20261006.json`
（`missed=0`，`expected` 里那 5 条是新候选 id），对应页面口径的
`artifacts/b_eval/relation_score_gold_20261006.json`。
这不是把标尺改短：gold 仍然**先从源头枚举**（事件字段 + 副本 NVD 快照），再按内容匹配候选；
只有"源头声明过 + 人工核验为 positive"才进 `expected`，系统多吐候选不会让分母变大，
而且旧 5 个 id 被 `resolved_former_ids` 显式映射（`tests/test_b_relation_cvss_recheck.py`
对此有防伪断言，含"改一个向量字段就必须核验失败"的反例测试）。
10-04 的 gold 与两份旧评分文件**保持冻结、字节不变**（LF 归一化 SHA256 已固定进测试），
作为"修复前"的对照基线。

### 11.6 本批次局限

* 仍是**抽样穷尽**：范围同第 2 节的 11 个对象，未扩样；
* 本轮 NVD 数据只覆盖 3 个目标 CVE（按 CVE 定向拉取），不是全量 NVD 同步；
* `poc` 与 `asset_assessment` 仍单列（真实库无资产 → `asset_assessment` 候选为 0，
  工具已如实报为覆盖缺口）；
* 新增的 6 条 cvss 候选中，5 条在抽样范围内已核验；范围外新增的 1 条仍为
  `pending_human_review`，不计入任何分母；
* 页面口径的 **Recall / F1 = 100% 只代表当前评测范围**（第 2 节那 11 个对象、4 个维度、
  抽样穷尽口径），**不代表全语料召回率**；范围内仍以 `pending_human_review` 单列，
  范围外不做任何推算。
