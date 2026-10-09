# B: relation candidate re-run and CVSS miss re-check

分支：`feat/b-relation-cvss-recheck-20261006`（自 `origin/main@b3e09b3`）。以下内容可直接作为 PR 描述。

## 背景

2026-10-04 的关系金标准识别出 5 条 `cvss` 漏检（FN），根因是采集链路只把 NVD 的 Exploit 引用
回填到 `poc[]`、丢弃了 CVSS `metrics`（CISA KEV 采集的事件 `cvss[]` 为空）。该问题已由
`6d15d31` 修复（`tools/backfill_nvd_poc.py` 现在同时合并 `cvss`，`app/storage.py` 新增
`merge_event_cvss()`）。修复只改了链路，而候选集是冻结产物，分数不会自己变。本 PR 把数据修复
转成真实分数。

## 做法

1. 复制真实库 `D:\ICT\intel-data-b` 为副本，按 CVE 定向请求 NVD CVE API 2.0
   （`CVE-2026-64849` / `CVE-2025-62593` / `CVE-2026-33017`），原始响应落盘并记 SHA256；
2. 跑修复后的 `tools/backfill_nvd_poc.py`：`cvss_events_updated=4`；
3. 重跑候选：`evaluation/b_relation_candidates_20261006.json`（四维候选 121 → 127，`cvss` 22 → 28）；
4. 新增 `tools/relabel_b_relation_candidates.py`，按关系内容（不是 id）把上一批次 121 条人工标注
   迁移到新候选（121/121 命中），再对本轮 5 条新 `cvss` 关系写入人工核验标注；
5. 新增 `tools/verify_b_relation_cvss_recheck.py`：把旧 5 个合成 id 逐条对应到新候选——
   主体 / 关系类型 / 对象 / 证据共 11 项检查，输出 `resolved_former_ids`；
6. 按同一协议、同一抽样范围重跑 gold：`evaluation/b_relation_gold_20261006.json`
   （带 `resolved_former_ids`，`missed=0`）；
7. 评分两份：页面口径 `relation_score_gold_20261006.json`（gold `_20261006`）与对照口径
   `relation_score_gold_frozen20261004_20261006.json`（gold `_20261004`）。

## 人工核验（5/5）

逐条把库内 `cvss[].vector` 与金标准期望向量逐字符比对，并确认该向量逐字出现在 NVD 官方
快照原文（可回读）：

| 原 gold id | 事件 | 新候选 id | 库内命中 | 快照可回读 |
|---|---|---|---|---|
| `BREL-GOLD-FN-CV-0001` | CVE-2026-64849 | `BREL-CV-0021` | 是 | 是 |
| `BREL-GOLD-FN-CV-0002` | CVE-2025-62593 | `BREL-CV-0022` | 是 | 是 |
| `BREL-GOLD-FN-CV-0003` | CVE-2025-62593 | `BREL-CV-0023` | 是 | 是 |
| `BREL-GOLD-FN-CV-0004` | CVE-2026-33017 | `BREL-CV-0024` | 是 | 是 |
| `BREL-GOLD-FN-CV-0005` | CVE-2026-33017 | `BREL-CV-0025` | 是 | 是 |

只有这 5 条被置为 `human_verified`（署名 `人工复核-用户确认` / `2026-10-09`）；其余候选保持原
状态，范围外新增的 1 条仍是 `pending_human_review`，不计入任何分母。

一一对应不是口头结论：`tools/verify_b_relation_cvss_recheck.py` 逐条核验主体 / 关系类型 /
对象 / 证据（每条 11 项检查全通过），映射写进 gold 的 `resolved_former_ids`；
把候选向量改一个字段，核验就会失败 —— `tests/test_b_relation_cvss_recheck.py` 里就有这条反例，
防止检查变成摆设。

## 指标（两种口径，不要混引）

| 口径 | 输入 | gold | TP | FP | FN | P | R | F1 |
|---|---|---|---|---|---|---|---|---|
| 10-04 冻结基线 | 121 条 | `gold_20261004` | 47 | 0 | 5 | 1.0 | 0.9038 | 0.9495 |
| 本批次（页面口径，active） | 标注 `_20261006` | `gold_20261006` | 52 | 0 | 0 | 1.0 | 1.0 | 1.0 |
| 本批次（对照口径） | 标注 `_20261006` | `gold_20261004` | 52 | 0 | 5 | 1.0 | 0.9123 | 0.9541 |

两份文件都写了 `input_source` / `gold_source`，不会看错来源；对照口径那份带 `frozen` 前缀，
因此不会被 `_active_relation()` 的正则选中、抢不到页面。`cvss` 维度：TP 10 → 15，FN 5 → 0。

为什么字面命令下 FN 仍为 5：评分器的 FN 判定按 `relation_id` 比对
（`missing_ids = expected_ids - 已验证 positive 的 id`）。10-04 的 gold 冻结了 5 个合成 id
（`BREL-GOLD-FN-CV-0001..0005`）作为应抽取全集；修复后系统抽出的这 5 条关系拿到新 id
（`BREL-CV-0021..0025`），旧 id 无从匹配，所以按 id 计仍为 FN。数据侧漏检已真实收敛
（TP 47 → 52、cvss FN 5 → 0），未收敛的是表示层（旧 gold 的 id 与修复后候选 id 不同源）。
要让 FN 指标也收敛到 0，需要把 gold 的 expected 改指向真实候选 id，即本 PR 附带的
`evaluation/b_relation_gold_20261006.json`。这不是把标尺改短：该 gold 由**同一工具、同一协议**
重跑（先从源头枚举事件字段与副本 NVD 快照，再按内容匹配候选），只有"源头声明过 + 人工核验为
positive"才进 `expected`，系统多吐候选不会让分母变大；旧 5 个 id 由 `resolved_former_ids`
显式映射，不是删除。

## 交付物

```
evaluation/b_relation_candidates_20261006.json                     重跑候选集
evaluation/b_relation_gold_20261006.json                           重跑 gold（missed=0，带 resolved_former_ids 映射）
artifacts/b_eval/relation_candidates_labeled_20261006.json         人工核验后的标注（含 verified_by/verified_at）
artifacts/b_eval/relation_new_positive_proposals_20261006.json     5 条新增 positive 的清单与证据
artifacts/b_eval/relation_cvss_recheck_verification_20261006.json  5/5 逐条核验（11 项检查，含快照 SHA256 与映射）
artifacts/b_eval/nvd_cvss_fetch_manifest_20261006.json             NVD 2.0 拉取清单
artifacts/b_eval/nvd_cvss_backfill_20261006.json                   回填报告
artifacts/b_eval/relation_score_gold_20261006.json                 页面口径评分（FN=0，R=F1=1.0）
artifacts/b_eval/relation_score_gold_frozen20261004_20261006.json  对照口径评分（对 10-04 冻结 gold，FN=5）
artifacts/b_eval/relation_missed_relations_20261006.json           本轮漏检清单（missed=0）
tools/relabel_b_relation_candidates.py                             按内容迁移标注的新工具
tools/verify_b_relation_cvss_recheck.py                            旧 id ↔ 新候选的逐条核验与映射
tools/build_b_relation_gold.py                                     支持 --system-output/--labeled-input/--former-missed，枚举去重
tools/score_b_relation_annotations.py                              评分文件记录 input_source / gold_source
docs/B_RELATION_GOLD_PROTOCOL.md                                   新增第 11 节（根因/修复/核验/口径/局限）
docs/B_RELATION_CVSS_RECHECK_CONCLUSION.md                         可写进报告的结论
tests/test_b_relation_cvss_recheck.py                              13 条回归测试（含防伪与冻结字节校验）
```

## 怎么验证（真实输出）

```
node --check app\static\app.js
exit=0

.\.venv\Scripts\python.exe -m pytest -q
1 failed, 648 passed, 1 warning in 151.98s

唯一失败项 tests/test_rag_mixed_language_query.py::test_mid_frequency_technical_terms_can_carry_a_query
改造前就存在；已在 origin/main 的独立 worktree 上复现同样失败，本 PR 未动 app/ 与 RAG。
```

复现：

```
.\.venv\Scripts\python.exe tools\backfill_nvd_poc.py --db <副本> --snapshot-dir <副本>\snapshots\nvd
.\.venv\Scripts\python.exe tools\build_b_relation_candidates.py --out evaluation\b_relation_candidates_20261006.json
.\.venv\Scripts\python.exe tools\relabel_b_relation_candidates.py --source artifacts\b_eval\relation_candidates_labeled_all.json --system evaluation\b_relation_candidates_20261006.json --out artifacts\b_eval\relation_candidates_labeled_20261006.json
.\.venv\Scripts\python.exe tools\verify_b_relation_cvss_recheck.py --db <副本>\intel.sqlite --snapshot-dir <副本>\snapshots\nvd --proposals-out artifacts\b_eval\relation_new_positive_proposals_20261006.json
.\.venv\Scripts\python.exe tools\build_b_relation_gold.py --db-dir <副本> --system-output evaluation\b_relation_candidates_20261006.json --labeled-input artifacts\b_eval\relation_candidates_labeled_20261006.json --former-missed artifacts\b_eval\relation_missed_relations_20261004.json --gold-out evaluation\b_relation_gold_20261006.json --missed-out artifacts\b_eval\relation_missed_relations_20261006.json --scope-input-out artifacts\b_eval\relation_candidates_labeled_gold_scope_20261006.json
.\.venv\Scripts\python.exe tools\score_b_relation_annotations.py --input artifacts\b_eval\relation_candidates_labeled_20261006.json --gold evaluation\b_relation_gold_20261006.json --out artifacts\b_eval\relation_score_gold_20261006.json
.\.venv\Scripts\python.exe tools\score_b_relation_annotations.py --input artifacts\b_eval\relation_candidates_labeled_20261006.json --gold evaluation\b_relation_gold_20261004.json --out artifacts\b_eval\relation_score_gold_frozen20261004_20261006.json
```

## 验收对照

| 验收项 | 结果 |
|---|---|
| 5 条 cvss 漏检全部转为 `human_verified` | 5/5，署名与日期齐备 |
| 新分数与 10-04 有明确变化且 P/R/F1 与 TP/FP/FN 自洽 | TP 47 → 52，FN 5 → 0，R 0.9038 → 1.0，测试逐项校验 |
| 旧 5 个 gold id 与新 5 个候选 id 一一对应 | 主体/关系类型/对象/证据逐条核验 5/5（11 项检查全通过） |
| 10-04 旧产物 0 改动 | LF 归一化 SHA256 固定进测试，逐文件校验字节不变 |
| 页面自动切到新批次（无需改代码） | `_active_relation()` 取最新日期 → `relation_score_gold_20261006.json`；`frozen` 对照文件不参与 |
| 全量测试通过 | 仅剩改造前既有、main 同样失败的 RAG 中频词 1 条 |

## 局限（不粉饰）

* 仍是抽样穷尽：范围同 10-04 的 11 个对象、4 个维度，未扩样；
* 本轮 NVD 数据只覆盖 3 个目标 CVE（按 CVE 定向拉取），副本快照目录只有 5 个 NVD 快照，
  回填 4 个事件，不是队长在多快照主机上跑出的更大规模结论；
* `poc` / `asset_assessment` 仍单列（真实库无资产，工具已如实报为覆盖缺口）；
* 页面口径的 Recall / F1 = 100% **只代表当前评测范围**（11 个对象、4 个维度、抽样穷尽），
  不代表全语料召回率；范围内未定项仍单列、范围外不做推算。

## 明确不做

* 不批量把候选标成 `human_verified` 刷分，只核验真正逐字符对照过向量的 5 条；
* 不修改或删除 10-04 的 gold 与两份旧评分产物。
