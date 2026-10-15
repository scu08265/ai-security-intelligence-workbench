# 报告数字一致性核对（2026-10-14）

**用途**：提交前最后一道闸——把技术报告与评分对照表里出现的每一个数字，逐条回指到证据来源。
对不上的直接列出并给正确值。

**比对源（2026-10-14 起，按队长口径）**：演示机读数一律以 `docs/report/metrics_snapshot.json`
为**唯一**比对源。它由 `python tools/refresh_metrics_snapshot.py --write` 同时重写
`docs/METRICS_BASELINE.md` 的快照块，因此**快照 JSON、基线文档、报告三处必须是同一组数**；
对不上就是某一处没刷新（`tests/test_metrics_snapshot.py` 会让它直接失败）。
数据自然增长导致的过期**不算口径变更**（`METRICS_BASELINE.md` §4.4），刷新即可，不用把报告退回旧值。

**当前快照**（`snapshot_date` = 2026-10-14）：`events 637`、`event_aliases 211`、`runs 1001`、
`assets / assessments / assessment_dispositions 8 / 190 / 6`、
`rag_documents / rag_chunks 1 / 849`、`duplicate_candidates 210`；
累计采集日 **20**、累计定时运行 **10 天**、`continuous_target_met = false`、
时效性 `p50 = 15.69 小时`（296 个有效样本）、处置闭环 48 / 4 / 8.33%；
关系 P 1.0 / R 0.734 / F1 0.8466。

**核对对象**

* `docs/report/AI安全知识情报系统技术报告.docx`（同名 pdf 同源，数字一致）
* `docs/COMPETITION_RUBRIC_MAPPING.md`

**方法**：从 docx 正文与表格抽出全部数值 token，逐个回查证据并重算。B 侧证据一律本机实算；
演示机读数与快照 JSON 逐字段比对。

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
| 术语可达 29/31 | 对照表 §2/§3/§4、§5 | 同上 `→ counts.term_reachable / term_not_reachable` | 一致（本分支新增进报告） |
| 关系 Precision 1.0 / Recall 0.734 | 关键数字表、第十章、对照表 §2/§3 | `artifacts/b_eval/relation_score_gold_20261010.json → micro` | 一致 |
| 可判定样本 94 条 | 同上 | 同上 `→ micro.evaluable_samples` | 一致 |

## 2. 演示机数字：与快照 JSON 逐字段比对

| 数字 | 出现位置 | 与 `metrics_snapshot.json` 比对 | 结论 |
| --- | --- | --- | --- |
| 语料规模（事件数） | 关键数字表 | 报告已改为读 `scorecard.events_total` = 637 | 一致（快照驱动） |
| 连续监测天数 | 关键数字表、第十章 | 报告读 `cumulative_actual_run_days` = 20 / `cumulative_scheduled_run_days` = 10 | 一致 |
| 连续运行目标 | 第十章 | 报告读 `continuous_target_met`；当前 `false`，文案已改为"当前窗口未达成" | 一致；**false 不是 bug** |
| 监测时效性 p50 | 关键数字表、第十章 | 报告读 `latency_p50_hours` = 15.69 | 一致 |
| 有效样本数 | 第十章 | 报告读 `effective_denominator` = 296 | 一致 |
| 处置闭环 48 / 4 / 8.33% | 关键数字表 | 快照 `disposition` = 48 / 4 / 0.0833 | 一致 |
| 去重候选 210 条 | 第三章 | 快照 `database.counts.duplicate_candidates` = 210 | 一致 |
| 容器验收 9 项 | 关键数字表 | `reports/docker-validation.json` | 一致 |
| 语料规模（分块）3,639 | 关键数字表（原与事件数同格） | 3,639 是 **B 评测语料**的 `rag_chunks`；快照里演示机是 1 文档 / 849 分块 | 已拆行，各带数据集限定语 |
| 来源产出 273 / 202 / 91 / 108 / 26 / 10 / 35 / 114 / 36 / 7 | 第三章来源表 | 快照里**没有**这些字段 | **仍写死**，见 §7 |
| 六维覆盖 388 / 150 / 101 / 74 / 48 / 26（分母 596） | 第四章 | 快照只有 `enrichment_sample` = 637；六个分子不在快照里 | **仍写死且分母过期**，见 §7 |
| 6 角色 / 455 次工具调用 / 781 条运行记录 / 112 次计划任务 | 第二章 | 快照里没有这些字段 | **仍写死**，见 §7 |
| ~~596 个事件 / 19 个采集日 与基线 548 / 18 对不上~~ | — | **已由 `df90eaf` 解决**：两者都是相隔一天的实时读数，现统一由快照 JSON 驱动，当前为 637 / 20 | 已闭环 |

## 3. 曾经列出的三处问题：现状

| 原问题 | 现状 |
| --- | --- |
| 1. 自动化测试 675 通过 / 4 跳过 | **上游已改**：现在写 **691 通过 / 4 跳过**，而 `df90eaf` 自己新增的测试没同步进去——实际应为 **694 通过 / 4 跳过**（本机语料齐全时 698 passed / 0 skipped）。交付衍生副本后应为 **698 passed / 0 skipped**。我原先按 10-13 任务书建议的 682 已作废 |
| 2. 语料规模一行把两个数据集并在一格 | **已解决**：该行改由快照驱动；B 评测语料的分块数在正文单列并带数据集限定语 |
| 3. 596 事件 / 19 采集日 与基线 548 / 18 对不上 | **已闭环**，见 §2 末行 |

## 4. 次要项

* **问答延迟 P95**：报告第十章原只写"分位数按批次独立统计"，没有数值。我在生成器里补上了实测值
  （`formal_qa_results_20261012.json → latency_ms`：p50 449.9 ms / p95 627.9 ms / max 709.4 ms，50 个样本）。
* **术语可达 29/31**：报告原本没有这个数。我在生成器第五章与边界段补上，并写明
  "属检索覆盖、与 10/21 分列不合并"。
* **docx/pdf 的重生成顺序**：`df90eaf` 已经重生成过一版（随快照机制落地），但那一版**不含**上面两条，
  因为本分支尚未合并。**正确顺序是先合并本分支，再由生成方重跑 `tools/build_technical_report.py`**；
  否则重生成的报告会缺 29/31 与 P95。

## 5. 快照怎么刷新（原建议已被上游实现）

我原先建议"把演示机读数落成一份 JSON 快照放进 `reports/`"。上游已用更彻底的方式实现了：
`python tools/refresh_metrics_snapshot.py --write` 同时重写 `METRICS_BASELINE.md` 的快照块与
`docs/report/metrics_snapshot.json`，报告生成器读同一个 JSON，`tests/test_metrics_snapshot.py` 守护两者同步。
提交前跑一次即可，不需要手工核对两处。

## 6. 2026-10-14 新增待核对项

任务书 2026-10-14 的 B5 另外点名四组数，逐条核如下。

| 数字 | 出现位置 | 证据路径 | 结论 |
| --- | --- | --- | --- |
| 术语字典 **14 个种子 / 10 个已覆盖 / 关联 44 份文档** | `docs/COMPETITION_RUBRIC_MAPPING.md` §5 | `GET /api/knowledge/terms` → `coverage()` 的 `terms / covered_terms / documents_referenced`；算法在 `app/term_dictionary.py` | **已过期**：本轮 B2 领域复核把种子由 14 扩到 **26** 条，"14 个 / 10 个"不再成立。§5 已改为"26 条 + 覆盖数以接口返回为准"；26 条在 B 评测语料（3,639 分块 + 93 事件）上实测 **25 覆盖 / 37 文档**，演示机需用同一接口重取。明细见 `docs/B_TERM_SEED_REVIEW.md` |
| 模型链 **三级** | 同上 §5；报告"模型降级链与角色绑定表" | `app/model_chain.py::chain()` → `levels` 恰为 3 项（1 远端模型协助 / 2 模型计划+本地拼装 / 3 本地确定性抽取），`role_bindings` 7 个角色 | 一致（3 级） |
| 推荐问法 **38 道可提问** | 同上 §5 | `/api/qa/suggestions`（`app/api.py`）取 `evaluation/b_formal_qa_set.json` 并跳过 `should_refuse`：50 − 12 = **38** | 一致 |
| 自愈演练 **四项断言** | 报告"可复现的自愈演练" | `tools/run_self_healing_drill.py:139-149` 的四个键；产物 `reports/self-healing-drill.json → assertions` 与 `verified` | 一致（4 项） |

**另需注意一处容易读成矛盾的地方**：`app/model_chain.py` 的说明写着"本系统没有本地模型层
（如 Ollama / 本地权重）"，而语料里 `ollama` 命中 3 个文档 / 24 条记录（本轮 B2 已把它加进术语表）。
两者不冲突：前者说的是**本系统不跑本地模型**，后者说的是**语料在讨论 Ollama 这个主题**。
报告与答辩引用时要带上这层限定，避免被读成"系统用了 Ollama"。

## 7. 闭环核对与新增发现（2026-10-15，以快照为唯一源）

### 7.1 上一轮报出的四条：全部闭环

| 上轮报出的问题 | 修复方式 | 结论 |
| --- | --- | --- |
| 第四章富化覆盖率表写死 `388 / 596`… | 改为 `_enrichment_row()` 读 `_snap("enrichment", "dimensions")` | **闭环** |
| 第十章 A1 时效性归因段写死 `18.1 小时 / 267 样本` | 改为读 `_snap('scorecard', 'latency_p50_hours')` 与 `effective_denominator` | **闭环** |
| 第十章自动化测试写死 `691 通过 / 4 跳过` | 快照新增 `tests` 字段（现为 702 passed / 0 skipped / 0 failed），报告改用 `_snap("tests")` | **闭环** |
| 口径表 §3 写死"连续 19 天采集证据" | 改为"不写死天数，看 `docs/METRICS_BASELINE.md` §2 的 `cumulative_actual_run_days` 与 `target_met`" | **闭环** |
| （上轮未列到）附录 A 写死"14 张术语卡" | 改为 `_term_dictionary_line()` 读 `GET /api/knowledge/terms` 的 `coverage.terms / covered_terms` | **闭环** |

复核基线：`docs/report/metrics_snapshot.json`（`snapshot_date` = 2026-10-14）；
五项都能追到快照或接口，不再有写死的演示机数字。

### 7.2 本轮新发现：四类数字仍然不在快照里

快照现有块为 `database / scorecard / disposition / relation / latency_by_class / enrichment / tests`。
下面四类仍写死在生成器里，**不在任何快照块中**，因此守卫测试看不见、也不会随库增长自动更新：

| 位置 | 现写死 | 问题 |
| --- | --- | --- |
| 第二章与第三章（两处） | "登记 20 个来源、覆盖 11 个类别，实际产出 15 个来源" | 来源数是演示机读数，快照里没有 `sources` 块 |
| 第二章 | "6 个角色共产生 455 次工具调用，781 条运行记录，其中 112 次由外部计划任务触发" | 快照里没有 `roles` / `runs` 块（`database.runs` 是运行记录总数，与这里的"781 条"不是同一口径，需一并澄清） |
| 图 3 的说明文字 | "小时间隔采集 / **19 个推荐来源**" | 与上面两处同源却数不一致（登记 20 / 产出 15 / 图上 19），三者至少要统一到同一口径 |
| 第十章的 B 侧两条 | "引用命中 0.9722 / 预期词命中 0.9211"、"关系 Precision 1.0 / Recall 0.734、94 条可判定样本" | 这两个来自 B 侧批次产物（`formal_qa_results_20261012.json`、`relation_score_gold_20261010.json`），不属于演示机快照；B 批次再变就会过期，建议加一句批次限定语 |

**建议**：给 `tools/refresh_metrics_snapshot.py` 增加 `sources` 与 `roles` 两个块
（来源登记数 / 类别数 / 产出数；角色数 / 工具调用数 / 运行记录数 / 外部触发数），
把前三类接上快照；B 侧两条加批次限定语即可，不必进快照。

**仍然成立的一条**：快照 `continuous_target_met = false` 是**事实**，不是 bug——计划任务窗口
2026-10-11 到期后 10-12 无计划运行，连续天数已重新起算。核对时不要当成错误。
