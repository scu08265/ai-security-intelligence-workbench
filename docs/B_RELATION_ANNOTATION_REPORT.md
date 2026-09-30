# B 任务 · 关系富化标注候选与 TP/FP/FN 工具

| 项 | 值 |
| --- | --- |
| 日期 | 2026-09-30 |
| 候选文件 | `evaluation/b_relation_candidates.json`（**121 条**） |
| 生成器 | `tools/build_b_relation_candidates.py` |
| 统计程序 | `tools/score_b_relation_annotations.py`（输出 `artifacts/b_eval/relation_score.json`） |

## 1. 目标与现状

目标：**至少 100 条人工核验的富化关系 + TP/FP/FN 统计**。

现状：**候选 121 条已生成；人工核验 0 条；TP/FP/FN 不可计算。**

## 2. 六维覆盖

| 维度 | 候选数 | 数据来源 | 可否评测 |
| --- | ---: | --- | --- |
| paper_link | **37** | `event.paper.pdf_url` / `arxiv_id` | 可（需人工核验） |
| version_range | **50** | `affected[].range` + package + ecosystem | 可（需人工核验） |
| fixed_version | **12** | `affected[].fixed_version` | 可（需人工核验） |
| cvss | **22** | `cvss[].score/vector/source_id` | 可（需人工核验） |
| **poc** | **0** | — | **不可评测** |
| **asset_assessment** | **0** | — | **不可评测** |
| 合计 | **121** | | |

### 覆盖缺口（工具已在 `coverage_gaps` 中输出）

1. **POC = 0**：14 个登记来源中没有任何专门的 POC 采集逻辑，事件 `poc` 字段全为空。
   按赛题口径，该维度在当前数据下**无法评测**，不得用 0 当作衡量系统能力的分数。
2. **资产关联 = 0**：资产表 **0 条**记录，没有可匹配资产，因此没有任何资产研判记录。

## 3. 每条候选的字段

`relation_id`（稳定 ID）/ `dimension` / `subject` / `relation` / `object` /
`candidate_value` / `evidence` / `verification_method` / `annotation{status,label,verified_by,verified_at,note}` /
`uncertainty`。

`annotation.status` 一律 `pending_human_review`，`annotation.label` 一律 `null`，
等待人工填写 `positive` / `negative` / `unknown` / `not_applicable`。

## 4. TP/FP/FN 判定规则（写在程序里，不可事后调整）

* 只有 `annotation.status == "human_verified"` 且 `label` 明确的候选进入统计；
* `positive` = 金标准正例；`negative` = 金标准负例；
* `unknown` / `not_applicable` **单列**，不计入任何分母；
* `pending_human_review` **不计入任何分母**；
* 系统侧预测取 `prediction.verdict`（`present` / `missing`）：
  * positive + present → **TP**
  * negative + present → **FP**
  * positive + missing → **FN**
  * negative + missing → **TN**
* 同时报告**微平均**（六维汇总）与**宏平均**（六维各自 P/R 的算术平均）。

## 5. 实测输出

```
computable: false
per_dimension: cvss(22 pending) / fixed_version(12) / paper_link(37) / version_range(50)
               全部 pending，TP=FP=FN=0
micro: precision=null recall=null evaluable_samples=0
macro: precision=null recall=null dimensions_with_metrics=0
note: 当前没有任何人工核验标注，TP/FP/FN 不可计算
```

程序**不会**在无标注时输出 0 或 100%——它显式返回 `null` 并说明原因。

## 6. 人工标注的下一步

1. 打开 `evaluation/b_relation_candidates.json`，按 `dimension` 分组逐条审核；
2. 按 `verification_method` 字段给出的方法对照来源原文；
3. 填写 `annotation.status = "human_verified"` 与 `annotation.label`；
4. 运行 `python tools/score_b_relation_annotations.py --out artifacts/b_eval/relation_score.json`
   得到分维度与微/宏平均 P/R。

**在完成人工填写之前，本任务"100 条人工核验关系"的目标完成度为 0%。**

---

# 人工标注指南（2026-09-30 补充）

本节把标注流程补到"可以直接交给人工填写"的程度。**原始候选文件与既有工作表均未改动。**

## 1. 你要填哪张表

| 文件 | 用途 | 允许覆盖 |
| --- | --- | --- |
| `evaluation/b_relation_candidates.json` | 原始候选（只读） | **禁止修改** |
| `artifacts/b_eval/relation_review_worksheet.csv` | 第一版复核表（历史） | 保留 |
| `artifacts/b_eval/relation_final_review_worksheet.csv` | 含自动结论的复核表 | 保留 |
| **`artifacts/b_eval/relation_annotation_worksheet_v2.csv`** | **本次交付的标注表（121 行，按优先级排序）** | **在此填写** |

每行都已包含：`relation_id`、`priority`、维度、主体/关系/客体、`source_id`、
`evidence_ids`、`evidence_summary`、`auto_judgment` + `auto_reason` + `rules_applied`、
`verification_method`、`uncertainty`，以及 4 个**空的人工列**。

## 2. 标签定义

| 标签 | 何时使用 |
| --- | --- |
| `positive` | 对照来源原文，**确认该关系成立**（例如 OSV 里就写着 `fixed: 0.30.0`，候选也是 `0.30.0`） |
| `negative` | 对照来源原文，**确认该关系不成立**（例如来源明确给出的是另一个修复版本） |
| `unknown` | 来源没有提供这条信息，或提供了但无法解读 |
| `not_applicable` | 该关系对本条事件不适用（例如不是这个生态的包） |

## 3. 常见情形的处理

| 情形 | 处理 |
| --- | --- |
| 证据不足（快照缺失、来源未收录） | 填 `unknown`，**不要**因为"没找到"就填 `negative` |
| 同一事实有多个版本/时间点 | 以**你实际核对的那份来源**为准，并在 `人工备注` 写明来源与时间 |
| 不同来源互相冲突 | 分别标注；冲突本身记在备注里，不要静默取一个 |
| 自动结论是 `contradicted` | 仍然独立核对原文后再填；不要直接抄 `auto_judgment` |
| `auto_judgment = insufficient_evidence` | 通常对应 `unknown`，但仍要看 `verification_method` 指出的证据位置 |
| 候选值格式可疑（如 `>= 0.24.0` 这种区间下界） | 若来源确实如此写，可判 `positive`，并在备注注明"区间下界语义" |

## 4. 三条硬性纪律

1. **不允许把 `auto_judgment` 直接复制成人工标签。** 自动核验只是待核对材料，不是结论。
2. **不允许留空却计入统计。** 空白 = 未核验，脚本不会把它算进任何分母。
3. 每条填了标签的行，都要填 `人工核验人` 与 `人工核验时间`；
   缺失时脚本会**警告**（不中止），但正式提交前应补齐。

## 5. 标注优先级

| 优先级 | 维度 | 条数 | 理由 |
| --- | --- | ---: | --- |
| **1-最高** | `fixed_version` | **12** | 证据最单一，`R-FV-STRUCTURED` 已与 OSV 结构化字段 1:1 比对；标完 precision 立即可算 |
| **2-高** | `cvss` | **22** | 字段明确（score + vector），22 条全部自动 supported |
| 3-中 | `version_range` | 50 | 12 条已通过结构化还原；其余多为厂商自有版本号 |
| 4-较低 | `paper_link` | 37 | 21 条因非 arXiv 未抓取正文，无法核对语义 |
| 5-缺数据 | `poc` / `asset_assessment` | 0 | 本地无数据源，**没有候选行可标** |

`relation_annotation_worksheet_v2.csv` 已按此顺序排好，**从第 1 行往下填即可**。

## 6. 标完之后怎么算指标

```powershell
# 第一步：把 CSV 里的标签回灌成评分脚本可读的 JSON（不覆盖原始候选）
.\.venv\Scripts\python.exe tools\apply_b_relation_labels.py `
    --worksheet artifacts\b_eval\relation_annotation_worksheet_v2.csv `
    --out artifacts\b_eval\relation_candidates_labeled.json

# 第二步：算分维度与微/宏平均的 TP/FP/FN、Precision
.\.venv\Scripts\python.exe tools\score_b_relation_annotations.py `
    --input artifacts\b_eval\relation_candidates_labeled.json `
    --out artifacts\b_eval\relation_score.json
```

回灌脚本会**拒绝**非法标签、重复 `relation_id`、候选里不存在的 `relation_id`，
不会静默丢弃。

## 7. Precision / Recall / F1 的可计算性

| 指标 | 何时可算 |
| --- | --- |
| **Precision** | 有任意 `positive`/`negative` 标签即可（`TP/(TP+FP)`） |
| **Recall、F1** | 还需要"**应当抽取的关系全集**"（`--gold`），否则 FN 没有来源 —— 候选集本身就是系统输出 |

`--gold` 文件格式：

```json
{"expected_relation_ids": {"BREL-FV-0001": "fixed_version"}}
```

## 8. 工具链测试

`tests/test_b_annotation_pipeline.py`（**16 项**）覆盖：空白标签、四种合法标签、
大小写/空格容错、非法标签中止、重复 ID 中止、未知 ID 中止、缺署名警告、
未标注行保持不变、CSV→JSON→指标的端到端、以及交付表的结构与排序。
