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

## 12. 2026-10-10 批次：关系评测扩样 + OSV 解析

### 12.1 扩样口径（2026-10-10 确认）

| 评测维度 | 原样本量 | 新样本量 | 采用方式 |
|---|---|---|---|
| `paper_link` | 3 篇 | 16 篇 | 16 篇论文全量纳入 |
| `version_range` / `fixed_version` | 2 个 | 12 个 | 12 个生态事件全量纳入 |
| CVE 相关关系 | 3 个 | 37 个 | 37 个 CVE 全量**盘点**，按证据覆盖分层 |

CVE 不按"有没有 NVD 快照"挑样本，也不把没有快照的样本直接算作 FN，而是分三层：

* **可核验样本（14）**：副本内有 NVD / MITRE 快照可回读，或事件自带 CVSS 向量 /
  非 `unknown` 区间。纳入正式 precision / recall / F1 计算。
* **证据不足样本（23）**：事件只有一个 `unknown` 区间（KEV 类来源不给版本边界），
  副本内没有 NVD / MITRE 快照。**只统计数量与原因，不进任何分母**。
* **新增漏检（25）**：源头明确声明、候选集里没有，且能从源头原字节**逐字回读**。
  约定是"经人工复核后才计入 FN"；本批次这 25 条完成了逐字回读，但**同样等人签核**
  （见 12.4），因此它们应被表述为"已验证的漏检"，而不是"已签核的漏检"。

**16 篇论文 / 12 个生态事件 / 37 个 CVE 是盘点范围，不代表全部进同一个分母。**
各维度的实际纳入量、证据覆盖量、排除量及排除原因都写在 gold 的 `scope` 里
（`inventory` / `tiers` / `enumerated` / `excluded_not_enumerable`），页面直接读它，
不按批次日推测。

### 12.2 新接入的源头（只翻译原文，不推断、不补全）

* **OSV**：`affected[].ranges[].events[]` 的 `introduced` / `fixed` / `last_affected`；
* **NVD**：`configurations[].nodes[].cpeMatch[]` 的 `versionStartIncluding` /
  `versionEndExcluding` 等版本边界（`versionEndExcluding` 即首个修复版本）；
* **MITRE CVE 记录**：`containers.cna.affected[].versions[].lessThan`（`< X` ⇒ 修复于 `X`）。

明确写清的**覆盖缺口**（不伪装成已覆盖）：

* OSV 批量查询响应里有 1901 条公告，但只有 `id` / `modified`，没有 `affected`，
  离线推不出区间；采集侧按预算只取回 12 条详情（`OSV_DETAIL_BUDGET = 12`）。
  **这是"搜不全"的真实缺口**，如实记进 `completeness.sources_not_covered`。
* NVD 快照只覆盖副本里已抓取的 5 个 CVE（`nvd_records_without_event = 398`）。

### 12.3 候选集零变化（分数变化只来自枚举口径）

`evaluation/b_relation_candidates_20261010.json` 与 `_20261006.json` **逐字节相同**
（SHA256 `415430c4…78ae53`，132 条）。因此本轮的分数变化**全部来自源头枚举口径**，
没有掺入任何候选集变化；`tests/test_b_relation_expansion.py` 对此有断言。

### 12.4 源头逐字回读核验（17 条，**待人工签核**）

`tools/verify_b_relation_expansion.py` 对"源头已声明、候选尚未判 positive"的关系逐条做
7 项检查（`event_exists` / `candidate_found` / `candidate_object_matches` /
`source_locator_resolves` / `source_value_matches` / `source_byte_rereadable` /
`annotation_not_contradictory`），任一项不过就 exit=1，不写"看起来没问题"的结论。

本批次核验 42 条：**可升级 17、被挡 0、新增漏检 25（其中源头不可回读 0）**。
17 条的构成：`cvss` 13 条（含 2 个生态事件此前为 `unknown` 的 cvss）、
`version_range` 2 条、`fixed_version` 2 条。

**这 17 条只过了工具核验，没有任何人工逐条确认**，因此：

* 它们的 `annotation.status` 是 `pending_human_review`，`label` / `verified_by` /
  `verified_at` 全为 `null`——**没有** `人工复核-用户确认` 签名；
* 待审核清单里的 `verified_by` 明确写着 `源快照逐字比对-待用户签核`，
  `signature_required = true`，即"证据已备好、结论还没签"；
* 只有签核人显式给出 `--verified-by` 之后，才允许用
  `relabel_b_relation_candidates.py --promote` 升级；撤回用 `--withhold`（同一份清单）一键回到
  `pending_human_review` 并清空签名，不需要手改 JSON。

核验记录：`artifacts/b_eval/relation_expansion_verification_20261010.json`；
待审核清单：`artifacts/b_eval/relation_new_positive_proposals_20261010.json`
（候选、源头证据、核验记录全部保留，撤回的只是"人工已确认"这个结论）。
注意 `--labeled` 必须指向**升级前**的标注状态（本批次用的是 `_20261006`），
否则已升级项会被跳过，得到 0 条 —— 那是自证而不是核验。

### 12.5 分数变化

| 口径 | 输入 | gold | TP | FP | FN | P | R | F1 |
|---|---|---|---|---|---|---|---|---|
| 10-04 冻结基线 | 121 条 | `gold_20261004` | 47 | 0 | 5 | 1.0 | 0.9038 | 0.9495 |
| 10-06 批次 | 132 条 | `gold_20261006` | 52 | 0 | 0 | 1.0 | 1.0 | 1.0 |
| **本批次（页面口径，active）** | 标注 `_20261010` | `gold_20261010` | **52** | 0 | **25** | 1.0 | **0.6753** | **0.8062** |
| 本批次（扩样前口径，对照） | 标注 `_20261010` | `gold_20261006` | 52 | 0 | 0 | 1.0 | 1.0 | 1.0 |

本批次标注状态：**人工核验 positive 52 条、`pending_human_review` 22 条**
（其中 17 条是上面待签核的关系，另外 5 条是 `poc` 维度的既有待审项）、
`human_verified/unknown` 58 条。`pending` 一律**不进任何分母**（既不计 TP 也不计 FN），
所以 active 的可判定样本是 77 条（52 + 25），而不是 132 条。

分维度（页面口径）：

| 维度 | TP | FP | FN | pending | P | R | F1 |
|---|---|---|---|---|---|---|---|
| `cvss` | 15 | 0 | 0 | 13 | 1.0 | 1.0 | 1.0 |
| `version_range` | 11 | 0 | 12 | 2 | 1.0 | 0.4783 | 0.6471 |
| `fixed_version` | 10 | 0 | 13 | 2 | 1.0 | 0.4348 | 0.6061 |
| `paper_link` | 16 | 0 | 0 | 0 | 1.0 | 1.0 | 1.0 |

**分数下降是扩样带来的，不是退化**：接入 OSV ranges / NVD configurations / MITRE
`lessThan` 之后，分母里第一次出现了"源头早就写着、系统一直没抽"的关系。
新增 25 条 FN 全部落在 `version_range` / `fixed_version`；`cvss` 维度在已签核的样本上
没有 FN。**这 17 条待签核关系不计入 TP 或 FN**：如果后续人工签核为 positive，
active 的 TP 会从 52 升到 69、Recall 从 0.6753 升到 0.734 —— 这是"等人确认"的差距，
不是系统抽取能力的差距。

同样要如实说明：25 条 FN 的**来源定位**已逐字回读，但同样没有逐条人工签核，
所以这两个数字是"可复现的机器证据结论"，签核后可能微调；本批次不为了让报表好看
而把未签核内容写进分子或分母。

### 12.6 本批次新识别的 25 条漏检

| 来源 | 事件 | 条数 | 为什么漏 |
|---|---|---|---|
| NVD `configurations` | CVE-2025-6558 | 18（9 平台 ×2） | 采集链路从未合并 NVD 的 `configurations`（CPE 产品 + 版本边界）；事件 `affected[].range` 只有 KEV 给的 `unknown` |
| NVD `configurations` | CVE-2025-62593 / CVE-2026-33017 / CVE-2026-64849 | 6 | 同上 |
| MITRE `lessThan` | CVE-2025-9959 | 1 | `app/normalize.mitre_to_event` 只把区间写进 `affected[].range`，`fixed_version` 一律留空 |

每条都带 `why_expected` / `why_missed` 与可回读的 `source_path` + `source_locator`
（不猜、不补）：见 `artifacts/b_eval/relation_missed_relations_20261010.json`。

### 12.7 页面口径

`_active_relation()` 自动取日期最大的 `relation_score_gold_*.json`，因此产出
`_20261010` 后页面自动切到新批次，**不需要改代码切批次**；
`_contrast_relation()` 自动接上 `relation_score_gold_frozen20261006_20261010.json`
（扩样前口径）。两者的 `scope` 都随金标准展示：盘点量、CVE 分层、
排除量与排除原因。页面文案明确写着"当前 Recall 只代表本批次的评测范围，
不代表全语料召回率"。

标签状态变化也反映到了页面上：`_relation()` 额外投影 `pending_samples`（未核验）与
`undetermined_samples`（无法定论），面板单列"待人工核验 / 无法定论"两行，
并在说明里写明**两者都不计入 Precision / Recall / F1 的任何分母**。
本批次页面显示：可判定 77 条、待人工核验 22 条、无法定论 58 条。

### 12.8 本批次局限

* 仍是**抽样穷尽**：16/12/37 是盘点范围，不是全语料；
* OSV 详情只取回 12 条（预算），批量响应里另外 1889 条公告离线枚举不出区间；
* NVD 快照只覆盖 5 个 CVE，23 个 KEV CVE 进"证据不足"层，不进分母；
* 10-06 的 gold 曾把事件字段里的 `unknown` 区间当作可比关系枚举（因此那 3 条落在
  `uncertain` 里）；10-10 起 `unknown` 一律记为"不可枚举"（`excluded_not_enumerable`），
  `--scope legacy` 仍能复现 10-06 的 `expected_relation_ids`，差异只在这一处；
* `poc` 与 `asset_assessment` 仍单列；
* 17 条待签核关系与 25 条已验证漏检都还没有逐条人工签核，因此本批次的两个分数是
  "机器 + 源头逐字回读"的结论，签核后可能微调；
* （已修复）`app/config.py` 曾在算完 `DATA_DIR` 之后才调用 `load_env_file()`，
  于是 `.env` 里的 `INTEL_DATA_DIR` 被忽略，命令行工具各自写死机器路径。
  现在 `load_env_file()` 在任何 `os.getenv` 之前执行，并新增
  `INTEL_ENV_FILE`（只改 .env 位置，不改优先级）；`tools/build_b_relation_gold.py`
  与 `tools/verify_b_relation_expansion.py` 的默认库目录改为复用
  `app.config.DATA_DIR`。优先级：显式环境变量 > `.env` > `BASE_DIR/data`。

### 12.9 复现命令

```powershell
$env:INTEL_DATA_DIR='D:\ICT\intel-data-b-cvss-20261006'   # 只读副本库

# 1) 候选集（与 10-06 逐字节相同，用来说明"分数变化不来自候选"）
.\.venv\Scripts\python.exe tools\build_b_relation_candidates.py `
    --out evaluation\b_relation_candidates_20261010.json

# 2) 核验"源头写着、候选还没判 positive"的关系（--labeled 用升级前的状态）
#    （标注迁移与落盘在第 3 步一次完成，这里不需要先写一遍中间文件）
#    不给 --verified-by 时，清单署名是"源快照逐字比对-待用户签核"
.\.venv\Scripts\python.exe tools\verify_b_relation_expansion.py `
    --db-dir D:\ICT\intel-data-b-cvss-20261006 `
    --candidates evaluation\b_relation_candidates_20261010.json `
    --labeled artifacts\b_eval\relation_candidates_labeled_20261006.json `
    --out artifacts\b_eval\relation_expansion_verification_20261010.json `
    --proposals-out artifacts\b_eval\relation_new_positive_proposals_20261010.json

# 3) 本批次采用的口径：17 条只过工具核验，停在 pending_human_review、不带签名
.\.venv\Scripts\python.exe tools\relabel_b_relation_candidates.py `
    --from artifacts\b_eval\relation_candidates_labeled_20261006.json `
    --system evaluation\b_relation_candidates_20261010.json `
    --withhold artifacts\b_eval\relation_new_positive_proposals_20261010.json `
    --out artifacts\b_eval\relation_candidates_labeled_20261010.json

# 4) 签核人逐条确认之后才升级（把上一步换成 --promote，并显式给出签名）：
#     python tools/verify_b_relation_expansion.py ... \
#         --verified-by <签核人> --verified-at <日期>
#     python tools/relabel_b_relation_candidates.py \
#         --from artifacts/b_eval/relation_candidates_labeled_20261006.json \
#         --system evaluation/b_relation_candidates_20261010.json \
#         --promote artifacts/b_eval/relation_new_positive_proposals_20261010.json \
#         --out artifacts/b_eval/relation_candidates_labeled_20261010.json

# 5) 重跑 gold 与两份评分（改标签后必须重跑，分数必须跟着标签走）
.\.venv\Scripts\python.exe tools\build_b_relation_gold.py `
    --db-dir D:\ICT\intel-data-b-cvss-20261006 `
    --system-output evaluation\b_relation_candidates_20261010.json `
    --labeled-input artifacts\b_eval\relation_candidates_labeled_20261010.json `
    --former-missed artifacts\b_eval\relation_missed_relations_20261006.json `
    --gold-out evaluation\b_relation_gold_20261010.json `
    --missed-out artifacts\b_eval\relation_missed_relations_20261010.json `
    --scope-input-out artifacts\b_eval\relation_candidates_labeled_gold_scope_20261010.json

.\.venv\Scripts\python.exe tools\score_b_relation_annotations.py `
    --input artifacts\b_eval\relation_candidates_labeled_20261010.json `
    --gold evaluation\b_relation_gold_20261010.json `
    --out artifacts\b_eval\relation_score_gold_20261010.json

.\.venv\Scripts\python.exe tools\score_b_relation_annotations.py `
    --input artifacts\b_eval\relation_candidates_labeled_20261010.json `
    --gold evaluation\b_relation_gold_20261006.json `
    --out artifacts\b_eval\relation_score_gold_frozen20261006_20261010.json
```

### 12.10 可写进报告的结论

> 本批次把关系评测的抽样口径从 11 个对象扩到 16 篇论文 / 12 个生态事件 / 37 个 CVE
> 的全量盘点，并把 OSV `ranges[].events`、NVD `configurations` 的版本边界、
> MITRE `lessThan` 三条源头声明正式接入枚举。CVE 按证据覆盖分层：14 个可核验样本
> 进入评分分母，23 个只声明 `unknown` 区间且副本内无权威快照的 KEV 条目单列数量与
> 原因、不进任何分母，避免把"无法核验"误算成漏检。候选集与上一批次逐字节相同
> （SHA256 一致），因此本轮分数变化全部来自枚举口径。
>
> 正式 gold（`evaluation/b_relation_gold_20261010.json`）只收两类：**人工核验为 positive
> 的候选（52 条，构成 TP）**与**源头逐字回读确认的真实漏检（25 条，构成 FN）**。
> active 评分（`artifacts/b_eval/relation_score_gold_20261010.json`）因此是
> TP 52 / FP 0 / FN 25、P 1.0 / R 0.6753 / F1 0.8062，可判定样本 77 条；
> frozen 对照（`relation_score_gold_frozen20261006_20261010.json`，同一批标注对
> 10-06 冻结 gold）是 TP 52 / FN 0 / R 1.0，两者只差"评测范围"这一个变量。
>
> 另有 17 条关系（13 条 `cvss`、2 条 `version_range`、2 条 `fixed_version`）已在源头
> 逐字回读通过 7 项核验，但**没有经过人工逐条签核**，因此保持在
> `pending_human_review`、不带 `human_verified` 签名，也**不计入任何分母**；
> 22 条未核验（含 5 条 `poc` 既有待审项）与 58 条"无法定论"同样单列。签核后这 17 条
> 可经 `--promote` 落地，届时 TP 由 52 升到 69、Recall 由 0.6753 升到 0.734。
>
> 25 条已验证漏检集中在 NVD `configurations`（24 条，根因是采集链路从未合并该字段）
> 与 MITRE `lessThan`（1 条，根因是 `fixed_version` 未从区间推导），每条都带可回读的
> 源头定位与 `why_expected` / `why_missed`（不猜、不补）。**本批次所有 Recall / F1 只代表
> 当前评测范围，不代表全语料召回率**；OSV 批量响应中另外 1889 条公告只带回
> `id`/`modified`、离线枚举不出修复版本，这一采集侧缺口已在 gold 的
> `completeness.sources_not_covered` 中如实记录。10-04 / 10-06 的冻结产物字节未变。
