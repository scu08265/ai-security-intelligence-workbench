# 报告数字一致性核对（2026-10-14）

**用途**：提交前最后一道闸——把技术报告与评分对照表里出现的每一个数字，逐条回指到
`artifacts/b_eval/`、`reports/`、`docs/METRICS_BASELINE.md` 或接口读数。对不上的直接给正确值。

**核对对象**

* `docs/report/AI安全知识情报系统技术报告.docx`（同名 pdf 同源，数字一致）
* `docs/COMPETITION_RUBRIC_MAPPING.md`

**方法**：从 docx 正文与表格抽出全部数值 token，再逐个回查证据文件并重算。
本机能读到的证据文件一律实算，不照抄；读不到的（演示机数据库读数）标为"本机不可核"。

## 1. B 侧数字：本机可逐条核验，全部一致

| 数字 | 出现位置 | 证据路径 | 结论 |
| --- | --- | --- | --- |
| 引用命中 0.9722（35/36） | 关键数字表、第五章、第十章 | `artifacts/b_eval/formal_qa_results_20261012.json → totals.document_hit` | 一致 |
| 预期词命中 0.9211（35/38） | 同上 | 同上 `→ totals.term_hit` | 一致 |
| 拒答一致率 0.84（42/50） | 第五章 | 同上 `→ totals.refusal_accuracy` | 一致 |
| 引用总数 222 | 第五章 | 同上 `→ totals.citations.total` | 一致 |
| 作答 / 拒答 46 / 4 | 第五章 | 同上 `→ totals.answered / refused` | 一致 |
| 修复前为 0.8889 | 第十章 | 用 `b020090` 在同一语料重跑复现，见 `docs/B_REEVAL_20261012_REPORT.md` | 一致 |
| 50 题构成 10/8/6/6/8/2/5/5 | 第五章 | `evaluation/b_formal_qa_set.json → cases[].category` | 一致 |
| 跨文档 10/21 | 概览、第五章、第十章、对照表 §2/§3 | `artifacts/b_eval/multihop_path_validation_20261002_v2.json → counts.by_chain_type.cross_document` | 一致 |
| 缺 52 条文档间边 | 同上 | 同上 `→ counts.missing_edge_kinds.document_to_document` | 一致 |
| 关系 Precision 1.0 / Recall 0.734 | 关键数字表、第十章、对照表 §2/§3 | `artifacts/b_eval/relation_score_gold_20261010.json → micro` | 一致 |
| 可判定样本 94 条 | 同上 | 同上 `→ micro.evaluable_samples` | 一致 |

## 2. 演示机数字：本机不可核，且有四处对不上

这些数取自演示机数据库/接口，本机没有那份库，因此只能做"与基线文档是否一致"的比对。

| 数字 | 出现位置 | 与基线文档比对 | 结论 |
| --- | --- | --- | --- |
| **596 个事件** | 关键数字表 | `docs/METRICS_BASELINE.md` §1 记录 **548**（2026-10-12 快照） | **对不上**：报告用了比基线更新的读数，但 §4 规则 1 要求"只放 §2 的数字并标注快照日期" |
| **3,639 分块** | 关键数字表（与 596 事件**同一行同一格**） | 3,639 是 **B 评测语料** `D:\ICT\intel-data-b` 的 `rag_chunks`；演示机库是 **1 个文档 / 849 分块**（§1） | **口径混引**：一行里放了两个不同数据集的数 |
| **累计 19 个采集日** | 关键数字表、第十章、对照表 §3 | §2 记录 **18 天**（2026-10-12 快照） | **对不上**：19 vs 18 |
| 定时运行 8 天 | 同上 | §2 记录 8 天 | 一致 |
| 处置闭环 48 / 4 / 8.33% | 关键数字表 | §2 记录 48 / 4 / 0.0833 | 一致 |
| 去重候选 210 条 | 第三章 | §1 记录 duplicate_candidates 210 | 一致 |
| p50 18.1 小时 / 267 个有效样本 | 关键数字表、第十章、对照表 §2 | 无仓库产物可回读；与 `docs/TASK_BRIEF_20261013.md` 记的同值 | 无证据文件，"演示机接口读数" |
| 来源产出 273 / 202 / 91 / 108 / 26 / 10 / 35 / 114 / 36 / 7 | 第三章来源表 | 无仓库产物 | 同上 |
| 六维覆盖 388 / 150 / 101 / 74 / 48 / 26（分母 596） | 第四章 | 无仓库产物；分母随 596 变 | 同上 |
| 6 个角色 / 455 次工具调用 / 781 条运行记录 / 112 次外部计划任务 | 第二章 | 无仓库产物 | 同上 |
| 容器验收 9 项 | 关键数字表、第十章 | `reports/docker-validation.json` | 一致（产物在库） |

## 3. 必须改的三处

1. **自动化测试 675 通过 / 4 跳过**（关键数字表与第十章各出现一次）
   → 应为 **682 通过 / 4 跳过**。675 出自 `docs/A_RAG_MIDFREQ_VERIFICATION.md` 的旧记录，
   而 `docs/TASK_BRIEF_20261013.md` 记的交付机现状是 682 / 4。
   4 条跳过需要两份衍生语料副本——这一点与事实相符（见 `docs/B_CORPUS_HANDOVER_REQUEST.md`）。
2. **语料规模一行把两个数据集并在一格**
   → 拆开：演示机库的"596 个事件"（或按基线文档的 548）与 B 评测语料的"3,639 个分块"分列，
   并各带数据集限定语。这直接违反 `docs/METRICS_BASELINE.md` §3"不得与上表混排在同一张指标表里"。
3. **596 个事件 / 19 个采集日 与基线文档的 548 / 18 对不上**
   → 二选一：先更新 `docs/METRICS_BASELINE.md` §1/§2 的快照（换机、换库、换语料按 §4 规则 3
   "先改本文件，再改下游文档"），或者报告回到 §2 的现有快照值并标注日期。

## 4. 次要项

* **报告正文没有给出问答延迟的 P95 实测值**，而 `docs/COMPETITION_RUBRIC_MAPPING.md` §2/§3
  写着"P95 延迟有实测"。证据是现成的：`formal_qa_results_20261012.json → latency_ms`
  （p50 449.9 ms / p95 627.9 ms / max 709.4 ms，50 个样本）。建议在第十章补一行。
* **报告尚未包含"术语可达 29/31"**。生成器 `tools/build_technical_report.py` 已补上
  （第五章与边界段，明确"属检索覆盖、与 10/21 分列不合并"），
  但 `docs/report/` 下的 docx/pdf **本轮没有重新生成**——该产物需要 matplotlib / reportlab /
  python-docx，本机环境不具备，且 A 正在为任务 A4 补状态机图后重生成报告。
  请由生成方在合入 A4 后统一重跑一次，本核对清单随之复验。
* 第十章"4 条跳过需要两份未交付的衍生语料副本"——与事实一致，无需改。

## 5. 本机不可核的部分怎么补

演示机读数需要在那台机器上取，建议一次性把下面的读数落成一份 JSON 快照放进 `reports/`，
之后报告只引这份快照（与 `docs/METRICS_BASELINE.md` §2 同源）：

```powershell
# 演示机
curl.exe -s http://127.0.0.1:8000/api/competition/scorecard   # 语料规模、连续运行、处置闭环、时效性
curl.exe -s http://127.0.0.1:8000/api/sources                 # 登记来源数、类别数、实际产出数
curl.exe -s http://127.0.0.1:8000/api/system/health           # 模块状态、活跃降级
```

取到后写进 `reports/scorecard-snapshot-<日期>.json`，并在 `docs/METRICS_BASELINE.md` §2 更新快照日期。
