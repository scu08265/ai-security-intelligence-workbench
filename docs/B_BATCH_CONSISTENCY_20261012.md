# B 项批次一致性说明（问答下游产物刷新到 10-12 批次）

**一句话**：问答下游的**机器产物**已整体切到 `formal_qa_results_20261012.json`（10-12 批次），
**人工标签产物一个字节都没动**。两者之间有一条明确的线，任何时候都不要把线两侧的东西混在一张表里。

任务书 2026-10-13 的 B2 决定"刷新"，本文件是它的验收物：逐个下游产物写清现在消费的是哪个批次，
并给出"人工标签是否需要重签"的判断与依据。

## 1. 为什么会有三代批次

| 批次 | 机器结果文件 | 说明 |
| --- | --- | --- |
| 09-30 基线 | `formal_qa_results.json` | 历史基线；人工列（50 题）判的就是这一批 |
| 10-02 批次 | `formal_qa_results_20261002.json` | `8db19cf` 改造 RAG 链路后的重评测批次 |
| **10-12 批次** | `formal_qa_results_20261012.json` | A1（`9ff7383`）排序修复后的结果，**本说明生效后的当前机器批次** |

差异来源已单独查证：用 A1 之前的 `b020090` 在同一份语料上重跑，**逐项复现**了 10-02 批次的数字，
因此 10-12 与 10-02 之间的差异可确定性归因于 A1，不是机器或语料漂移。逐题差异见
`docs/B_REEVAL_20261012_REPORT.md`。

## 2. 只依赖机器结果的产物：本轮已刷新到 10-12

| 产物 | 生成工具 | 输入批次 | 本轮变化（09-30 → 10-12） |
| --- | --- | --- | --- |
| `qa_auto_review.json` | `tools/auto_review_qa.py` | 10-12 | supported 33 → 38；contradicted 4 → 6；insufficient_evidence 7 → 2；not_applicable 6 → 4；50 题里 34 条记录内容变化 |
| `refusal_failure_classification.json` | `tools/classify_b_refusals.py` | 10-12 | correctly_refused 6 → 4；wrongly_answered 6 → 8；needs_human_review 2 → 4 |
| `qa_candidate_answers.json` | `tools/build_b_qa_candidate_answers.py` | 10-12 | `with_citations` 35 → 42；50 题里 32 条候选答案变化 |
| `qa_machine_adjudication.json` / `.csv` | 同上 | 10-12 | 答案正确性建议 correct 15 → 25、partial 18 → 13、incorrect 5 → 0；引用支持性 pending 11 → 42 |
| `qa_pending_human_cases.csv` | 同上 | 10-12 | 待人工核验 16 → 44 条 |
| `qa_review_worksheet.csv` | `tools/build_b_review_workpackets.py` | 10-12 | 50 行；人工列仍是空的（见第 3 节） |
| `review_workpacket_summary.json` | 同上 | 10-12 | 路径字段指向仓库内真实文件 |
| `qa_performance_stats.json` | `tools/build_b_qa_performance_report.py` | 10-12 | 两个批次都换成 10-12：A = `formal_qa_results_20261012.json`（p50 449.9 / p95 627.9 ms），B = `formal_qa_performance_run2_20261012.json`（p50 450.1 / p95 569.9 ms）；逐题对照显示**作答/拒答结构无变化**，只有耗时波动 |
| `auto_review_summary.json` | `tools/summarise_auto_review.py` | 10-12 | qa_supported 33 → 38；qa_contradicted 4 → 6；qa_insufficient_evidence 7 → 2；qa_not_applicable 6 → 4；延迟来源改为 10-12 批次 |

新增的批次副本：`formal_qa_performance_run2_20261012.json`（10-12 的第二次运行，供性能对照）。

### 2.1 工具输入的落点

六个工具的默认输入已从 `formal_qa_results.json` 改为 `formal_qa_results_20261012.json`，
`--results` 参数保留可覆盖：

* `tools/auto_review_qa.py`（`RESULTS`）
* `tools/classify_b_refusals.py`（`RESULTS`）
* `tools/build_b_qa_candidate_answers.py`（`RESULTS`）
* `tools/build_b_review_workpackets.py`（`QA_RESULTS`）
* `tools/summarise_auto_review.py`（`QA_RESULTS`）
* `tools/build_b_qa_performance_report.py`（用法示例）

`tools/score_b_qa_annotations.py`（人工指标）**没有改**，它仍读 `formal_qa_results.json`，
见下一节的理由。

## 3. 依赖人工标签的产物：本轮一个字节都没动

这些文件的取值来自人工作业，机器重跑只会把人工列清空，因此**不参与本次刷新**：

| 产物 | 人工填写现状（2026-10-14 实测） |
| --- | --- |
| `qa_adjudication_table.csv` | 引用准确性 50/50、拒答正确性 50/50、核验人 50/50、答案正确性 33/50 |
| `qa_final_confirmation_worksheet.csv` | 核验人 50/50、答案正确性 33/50 |
| `qa_final_confirmation_worksheet_20261002.csv` | 核验人 50/50、答案正确性 38/50 |
| `qa_gold_standard_worksheet.csv` | 人工逐题金标准表 |
| `qa_human_score.json` / `qa_human_score_20261002.json` | 人工指标（署名 `人工复核-用户确认`） |
| `relation_annotation_worksheet_v2.csv` | 121/121 已签核（`人工核验人` / `人工核验时间` 全填） |

**执行时的保护措施**：`tools/build_b_review_workpackets.py` 与
`tools/build_b_qa_candidate_answers.py` 都会写人工工作表
（前者写 `relation_annotation_worksheet_v2.csv`，后者写 `qa_final_confirmation_worksheet*.csv`
与 `qa_adjudication_table.csv`）。因此本轮先把它们跑到临时目录，**只回拷纯机器文件**；
需要写回仓库路径的那一步（`review_workpacket_summary.json`），先对
`relation_annotation_worksheet_v2.csv` 取 SHA256、备份、跑完立即还原并复核：
`CCEC9F0A…505A52F0` → 覆盖后 `CFE8633E…61A4E6C8` → 还原后 `CCEC9F0A…505A52F0`，一致。

## 4. 人工标签是否需要重签

**结论：其余 46 题沿用，最多 4 题需要复核。**（任务书里的初判是"不需要重签"，这里给出更细的边界。）

依据是 A1 改变了这 4 题的**判定对象**，而人工列判的正是判定对象：

| 题号 | A1 之前被引用的文档 | A1 之后被引用的文档 | 受影响的人工列 |
| --- | --- | --- | --- |
| BQA-003 | `2501.13787`、`2609.29429`、`2609.30192` | `2501.13787`、**`2609.28900`** | 引用支持性 |
| BQA-005 | `2501.13787`、`2609.29429`、`2609.30192` | `2501.13787`、**`2609.29230`** | 引用支持性 |
| BQA-034 | `2501.13787`、`2609.29429`、`2609.30192` | **`2609.28900`**、**`2609.30028`** | 引用支持性 |
| BQA-002 | 引用集合未变 | 答案文本的预期要点命中变化 | 答案正确性（待复核） |

* 题目本身、期望答案、拒答要求都没变，所以**其余 46 题的人工判定仍然有效**，不需要重签。
* 这 4 题的人工判定是针对"当时那组引用 / 那份答案"下的；现在引用集合或答案文本变了，
  旧判定不再描述当前系统的输出。**这不是必须立刻重签**——只要在引用这两批数字时
  带上批次限定语，就不会出错；但若要把人工指标说成"当前系统的水平"，这 4 题必须重判。
* 重签与否属于产品决定，本轮**不代替任何人签字**：`qa_human_score.json` 与各工作表保持原样。

## 5. 刷新之后的一个已知口径分叉（需要队长知道）

**机器侧是 10-12，页面仍是 10-02。** `app/b_evaluation.py` 的 `_active_batch()` 要求
`qa_human_score_<8位日期>.json` 与 `qa_performance_<8位日期>.json` **成对存在**才切批次；
`qa_human_score.json` 内嵌的 `machine_metrics.source` 仍指向 `formal_qa_results_20261002.json`。
因此本次刷新**不会**让页面数字变化。

这本身不是错误（机器产物与人工指标本来就是两条线），但汇报时必须说清楚：**页面上那组问答人工指标
对应的是 10-02 批次**。若要让页面切到 10-12，需要再走一次"重签 4 题 + 产出
`qa_human_score_20261012.json` 与 `qa_performance_20261012.json`"的完整链，缺一不可。

## 6. 批次副本的保留

被覆盖的 09-30 批次内容已冻结为带日期后缀的副本，原文件不再承载唯一副本：

```
auto_review_summary_20260930.json          qa_pending_human_cases_20260930.csv
qa_auto_review_20260930.json               qa_performance_stats_20260930.json
qa_candidate_answers_20260930.json         qa_review_worksheet_20260930.csv
qa_machine_adjudication_20260930.json      refusal_failure_classification_20260930.json
qa_machine_adjudication_20260930.csv       review_workpacket_summary_20260930.json
```

命名刻意避开页面的批次日正则 `^(qa_human_score|qa_performance)_(\d{8})\.json$`，
因此不会参与 `_active_batch()` 的竞争。
