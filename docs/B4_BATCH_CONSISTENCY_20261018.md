# B4 批次一致性说明（2026-10-18）

**一句话**：正式对外的仍然是 **20261012 批次 / 2026-10-15 人工判定**；20261018 只有机器结果，
人工表 50 行全空。两边不得混引，页面也不会提前切批次。

## 1. 机器产物与批次

| 批次 | 机器结果 | 语料 | 说明 |
| --- | --- | --- | --- |
| 20261002 | `formal_qa_results_20261002.json` | `intel-data-b`（3,639 分块） | `8db19cf` 改造后第一次重跑；引用命中 0.8889 |
| 20261012 | `formal_qa_results_20261012.json` | 同上 | A1（`9ff7383`）同义词组计分后重跑；引用命中 0.9722、引用总数 222 |
| 20261018 | `formal_qa_results_20261018.json` | `intel-data-b-colfix-20261018`（22 文档 / 3,681 当前版本分块） | B1 抽取修复 + B2 重建语料后重跑；指标同值、引用总数 229；**无人工判定** |

10-18 机器结果：50 题、answered 46 / refused 4、errors 0 / timeouts 0、
document_hit 35/36 = 0.9722、term_hit 35/38 = 0.9211、refusal 42/50 = 0.84、
citations 229（retrievable 229）、p50 523.7 ms / p95 669.9 ms。

**确认表的一个已知限制**：`qa_final_confirmation_worksheet_20261018.csv` 的 `system_answer` 列由
`tools/build_b_qa_candidate_answers.py` 按 600 字符截断（超出部分以"…"结尾），50 行里有 21 行被截断。
截断只影响该列的显示，不影响批次来源（50 行其余机器列与 10-18 结果逐项一致：refused 50/50、
latency 50/50、ID 集合相同）。完整答案见 `artifacts/b_eval/B4_HUMAN_REVIEW_20261018.csv` 的
`old_answer_1012` / `new_answer_1018` 两列，或 `formal_qa_results_20261018.json → records[].answer_full`。

## 2. 人工标签与依赖关系

| 人工产物 | 批次 | 状态 | 依赖 |
| --- | --- | --- | --- |
| `qa_human_score_20261002.json` | 20261002 | 50/50 已签（2026-10-04） | 依赖 10-02 机器输出 |
| `qa_human_score_20261012.json` | 20261012 | 50/50 已签（2026-10-15，其中 4 题 10-15 重签） | 依赖 10-12 机器输出 |
| `qa_final_confirmation_worksheet_20261018.csv` | 20261018 | **50 行，人工列与署名全空** | 依赖 10-18 机器输出 |
| `qa_human_score_20261018.json` | 20261018 | **不存在** | 需人工签核后由 `score_b_qa_annotations.py` 生成 |
| `qa_performance_20261018.json` | 20261018 | **不存在** | 需机器性能汇总生成 |
| `relation_score_gold_20261010.json` | 20261010 | 已冻结（P 1.0 / R 0.734 / 94 条） | 不随问答批次变化 |

**结论**：10-18 的任何数字都只能写成"新一轮机器侧结果 / 待人工确认"，
不能写成当前代码的成绩，也不能替换 10-12 的引用。

## 3. 页面批次是怎么选的（代码事实）

`app/b_evaluation.py::_active_batch()` 扫描 `qa_*_<批次>.json`，只把**同时存在**
`qa_human_score_*` 与 `qa_performance_*` 的批次视为完整批次，取最大批次号。
当前完整批次只有 20261002 与 20261012，因此页面显示 **20261012**。

切到 10-18 的三个条件（缺一不可）：

1. 人工按 `docs/B_CITATION_SUPPORT_RUBRIC.md` 逐题签核 `qa_final_confirmation_worksheet_20261018.csv`；
2. `tools/apply_b_qa_labels.py` + `tools/score_b_qa_annotations.py` 产出 `qa_human_score_20261018.json`；
3. `tools/build_b_qa_performance_report.py` 产出 `qa_performance_20261018.json`。

只做第 2 步不做第 3 步，页面仍停在 1012；这就是"两份文件必须同时存在"的原因。

`_active_relation()` 取最新的 `relation_score_gold_<日期>.json`，当前是 20261010，与快照
`relation` 块（P 1.0 / R 0.734 / F1 0.8466 / TP 69 / FP 0 / FN 25）一致。

## 4. 混批检查（本轮发现并修掉）

| 位置 | 问题 | 处理 |
| --- | --- | --- |
| 技术报告关键数字标题 | 标题写 10-13 快照，表格读 10-18 | 标题改为读 `snapshot_date` |
| 技术报告附录 B | 声称"本表是 10-13 读数，与主表不同" | 表格改为快照驱动后失效，改为"与主表同一份快照（2026-10-18）" |
| 技术报告第五章 | 只写 10-12 数字，未说明 10-18 已重跑 | 补一句：10-18 三项同值、引用 229，人工未完成，正式结论仍用 10-12/10-15 |
| `COMPETITION_RUBRIC_MAPPING.md` | 头部 10-13、§2.1 写 10-14 快照读数 | 统一到 10-18 快照 |
| `METRICS_BASELINE.md` §2.1 | 仍写 297/15.58、1.75/8.34 | 改为 336/14.43、2.2/8.27；10-13 读数保留为历史 |
| `B_REPORT_NUMBER_AUDIT.md` | "当前快照"停在 10-14（637/20/15.69/296/48-4-8.33%） | 改为 10-18，10-14 值降为历史段 |
| `B_EVIDENCE_INDEX.md` | 测试数停在 698 | 补 748（本分支）/731（快照）/698（10-14）三个时点 |
| 技术报告术语字典 | 演示机 19/83/97 与本机构建会输出 0 | 只报种子 26 条并指向接口；对照表分语料列出三套读数 |

未发现：把 10-18 人工结果写成已完成、把 10-18 数字写进正式结论、把 10-12 旧产物覆盖的情况。

## 5. B3 三个口径分别核验（不合并）

来源：`artifacts/b_eval/multihop_path_validation_20261002_v2.json → counts`。

| 口径 | 读数 | 分母 | 含义 | 证据字段 |
| --- | --- | --- | --- | --- |
| 跨文档推理 | **10/21** | 21 条跨文档链，`no_path = 11` | 文档与文档之间是否存在可追溯的引用路径 | `by_chain_type.cross_document.{total,path_found,no_path}` |
| 术语可达 | **29/31** | 31 条候选，2 条不可达 | 给定术语能否在语料中被检索到（检索覆盖） | `term_reachable=29 / term_not_reachable=2` |
| 两跳推理 | **10/10** | 10 条两跳链 | 术语/事件两跳内的路径连通 | `by_chain_type.two_hop.{total,path_found}` |

缺失边：`document_to_document = 52`、`unspecified = 9`、`term_node_with_evidence = 2`。
**52 条文档间边是数据缺口**（语料里没有真实互引），不是代码缺陷；本轮没有补造任何边。
三者分母不同、含义不同，报告里分列，任一都不能替代跨文档推理。

## 6. 10-18 的 31 道变化题：归因与人工范围

* 31 题答案正文变化（BQA-001/002/003/004/005/006/007/010/011/012/014/015/016/017/019/020/021/
  023/025/026/028/029/030/031/032/034/040/044/047/048/049）。
* 引用文档集合只有 **BQA-047、BQA-048** 变化；其余 29 题引用文档不变，变化在答案组织与选句。
* **不是单一原因**：`ec57d09`（2026-10-17，"先结论后证据"）与 B1/B2 语料重建同时生效；
  未做单因素 A/B，不能把单题差异归给 PDF 抽取修复。
* 机器侧可判的事实（长度、引用条数、文档集合、document_hit/term_hit、拒答标记、首句是否截断）
  已逐题写进 `artifacts/b_eval/B4_HUMAN_REVIEW_20261018.csv`；
  引用是否支持答案、答案是否正确、拒答是否合理，必须按
  `docs/B_CITATION_SUPPORT_RUBRIC.md` 由人判断，CSV 中三列判定与署名保持空白。

## 7. 切批次前的检查清单

```powershell
# 1) 人工表 50 行、ID 唯一、人工列全空（签核前）
.\.venv\Scripts\python.exe - <<'PY'
import csv; rows=list(csv.DictReader(open(r'artifacts/b_eval/qa_final_confirmation_worksheet_20261018.csv',encoding='utf-8-sig')))
print(len(rows), len({r['question_id'] for r in rows}), sum(1 for r in rows if r['人工核验人'].strip()))
PY
# 2) 签核后：回灌 → 人工指标 → 性能统计（两份文件必须同时生成）
.\.venv\Scripts\python.exe tools\apply_b_qa_labels.py --help
.\.venv\Scripts\python.exe tools\score_b_qa_annotations.py --help
.\.venv\Scripts\python.exe tools\build_b_qa_performance_report.py --help
# 3) 页面批次自检
.\.venv\Scripts\python.exe -c "from app import b_evaluation; print(b_evaluation._active_batch())"
```

在 1–3 完成之前，任何汇报都必须写"20261012 批次、10-15 判定"，10-18 只能标"机器侧、待人工"。
