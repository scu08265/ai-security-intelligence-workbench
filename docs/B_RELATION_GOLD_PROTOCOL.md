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
