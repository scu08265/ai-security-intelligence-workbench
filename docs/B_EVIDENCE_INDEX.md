# B 任务证据索引（Evidence Index）

**用途**：把赛道 B 的五项要求映射到仓库中的**权威产物**，供评审与复现时快速定位。

**两条约定**：

1. **本文件不重复记录数字。** 任何指标的权威来源是下表列出的文件与字段路径；
   本文件只回答"去哪里看、按什么口径看、还缺什么"。
2. **机器指标与人工指标分列存放**，不合并、不互相替代（详见第 3 节口径说明）。

**运行环境**：仓库 `D:\ICT\ai-security-intelligence-workbench-git`，数据目录
`D:\ICT\intel-data-b`（全程只读）；产物根目录 `artifacts/b_eval/`、`docs/`、`tools/`。
冻结基线（2026-09-30 产出）在 `feat/b-evaluation` 及其合并记录中；重评测批次
（2026-10-02 产出，文件后缀 `_20261002`）在分支 `feat/b-reevaluation-20261002`（自 `8db19cf` 开）。

> **数据可达性（2026-10-12 / 10-14 更新）**：B 交付了主语料包 `B_CORPUS_20261012.zip`（整包 SHA-256
> `3aa9e9be…e76e42`），交付机按 `MANIFEST.sha256` 逐文件核验 47 / 47 通过，并还原到
> `D:\ICT\intel-data-b`（`intel.sqlite` = 8,183,808 B / `4095a5b1…8254285`，与上文记录一致）；
> 同日 B 侧另打包了 `B_DERIVATIVE_CORPORA_20261012.zip`（整包 SHA-256 `98bd19c5…961674a`，
> 80,208,714 字节，139 文件 / 172 条目，含 `intel-data-b-cvss-20261006` 与
> `intel-data-b-poc-20261002`，包内 `MANIFEST.sha256` 逐行 `<SHA256>  <字节数>  <相对路径>`）。
> **已交付并核验（2026-10-14）**：交付机按包内 `MANIFEST.sha256` 逐文件核验 **139 / 139 通过**，
> 两个主库哈希与记录一致（`FCD31963…` / `CEC88D75…`），落位后**跳过归零**。
> 主语料与两个衍生副本都已到位：**B 项评测可以在交付机上复跑验证**，不再只是引用历史数字。
> 测试数是**时点值**：主语料到位当天（10-12）由 618 passed / 60 skipped 变为 674 passed / 4 skipped；
> 此后测试集随主分支增长，衍生副本到位后为 **698 passed / 0 skipped / 0 failed**（本机语料齐全时实测同值）。
> 语料交接记录见 `docs/B_CORPUS_HANDOVER_REQUEST.md`。
> 语料本身仍不进仓库（`.gitignore` 排除 `data/*.sqlite*`），这是既定约定；
> 交付方式固定为整包外发 + 哈希核验。

---

## 1. 富化准确率与召回率评测

| 环节 | 权威产物 | 关键字段 / 口径 |
| --- | --- | --- |
| 候选关系集 | `evaluation/b_relation_candidates.json` | `cases[]`（每条含 `dimension / subject / relation / object / candidate_value / evidence`） |
| 人工标注表 | `artifacts/b_eval/relation_annotation_worksheet_v2.csv`（121 行）<br>`artifacts/b_eval/evidence_relation_label_sheet.csv`（34 行）<br>`artifacts/b_eval/evidence_remaining_label_sheet.csv`（87 行） | 列 `待人工填写_最终标签`（`positive/negative/unknown/not_applicable`）与 `人工核验人/时间/备注` |
| 回灌结果 | `artifacts/b_eval/relation_candidates_labeled_all.json` | `cases[].annotation.{status,label,verified_by,verified_at}` |
| 指标 | `artifacts/b_eval/relation_score_all.json` | `micro.{tp,fp,fn,precision}`、`per_dimension[维度].{total,tp,fp,undetermined,precision}`、`fn_source.available`（决定 recall/F1 是否可算） |
| 标注工作流 | `tools/apply_b_relation_labels.py`、`tools/score_b_relation_annotations.py` | 合法标签集、空白/unknown 处理规则写在脚本 docstring |
| 报告 | `docs/B_RELATION_ANNOTATION_REPORT.md`、`docs/B_EVIDENCE_PACKET_GUIDE.md`、`docs/B_AUTO_REVIEW_REPORT.md` | 维度定义、证据包生成、自动核验与人工标注的区别 |

**六维度覆盖与缺口**：以 `relation_score_all.json → per_dimension` 为准；
`poc` 与 `asset_assessment` 两个维度**无候选**（本地 `events[].poc[]` 为空、`assets` 表 0 条），
因此没有对应指标，而非指标为 0。

## 2. 跨文档与多跳推理评测

| 环节 | 权威产物 | 关键字段 / 口径 |
| --- | --- | --- |
| 题集 | `evaluation/b_multihop_candidates.json` | `cases[]`：问题、所需文档/实体、关系边、证据 ID、期望推理步骤 |
| 路径验证 | `artifacts/b_eval/multihop_path_validation.json` | `counts.by_chain_type`（连通/未连通）、`missing_edge_summary`（缺失边类型与次数）、`limitations` |
| **跨文档推理**（口径一） | `artifacts/b_eval/multihop_path_validation_*_v2.json` | `counts.by_chain_type.cross_document`：已连通 / 分母；缺口是 52 条 `document_to_document` 边。**不达标就不申报"跨文档推理"优秀档** |
| **术语可达**（口径二） | 同上 | `counts.term_reachable / term_not_reachable`：衡量"给定术语能否被语料检索到"，属**检索覆盖**，不是推理证据 |
| **术语 → 文档两跳**（口径三） | `GET /api/knowledge/terms` → `coverage.documents_referenced`；算法在 `app/term_dictionary.py::term_edges()` | 计数的是**术语命中了哪些文档**（A4 已接进知识图谱返回）。和口径二一样，不能替代口径一 |
| 结构化路径检索器 | `tools/multihop_path_retriever.py` | 输出**节点列表 / 边列表 / 每边证据 ID**；不输出隐藏思维链（脚本 docstring 有边界说明） |
| 测试 | `tests/test_b_multihop_candidates.py`、`tests/test_b_multihop_path.py` | 正例、反例、缺失证据、重复边 |
| 报告 | `docs/B_MULTIHOP_DATASET_REPORT.md` | 数据来源、构造规则、局限 |

**三个口径分列、不合并**：口径一是文档之间的引用，口径二是术语能否被检索到，口径三是术语命中了哪些文档。
引用时永远分开写，任一都不能替代口径一；判定细则与档位映射见 `docs/COMPETITION_RUBRIC_MAPPING.md` §4 与 §6。

## 3. 问答性能评测（50 题固定集）

| 环节 | 权威产物 | 关键字段 / 口径 |
| --- | --- | --- |
| 题集 | `evaluation/b_formal_qa_set.json` | `cases[]`：`question_id / category / question / should_refuse / expected_*` |
| 运行记录（两批，批次分开） | `artifacts/b_eval/formal_qa_results.json`（批次 A）<br>`artifacts/b_eval/formal_qa_performance_run2.json`（批次 B） | `records[]`：`answer_full / citations_detail / refused / latency_ms / timeout / error` |
| 跨批次性能统计 | `artifacts/b_eval/qa_performance_stats.json` | `batches[].latency_ms.{mean,p50,p95,min,max}`、`batches[].outcomes.{answered,refused,errors,timeouts,failures}`、`comparison.delta_ms`（**批次不合并**） |
| 人工金标准与指标 | `artifacts/b_eval/qa_human_score.json` | 数值字段：`answer.*`、`citation.*`、`refusal.*`、`by_category.*`、`target_comparison.metrics[]`；口径说明：同名文件 `note` 与报告 §16 |
| 人工标签表 | `artifacts/b_eval/qa_gold_standard_worksheet.csv`（50 题金标准表）<br>`qa_final_confirmation_worksheet.csv`、`qa_adjudication_table.csv` | 三列表：`人工判定_答案正确性 / 引用准确性 / 拒答正确性` + `人工核验人/时间/备注` |
| 机器辅助裁定 | `artifacts/b_eval/qa_machine_adjudication.{json,csv}`、`qa_candidate_answers.json` | `tier = B_machine_assisted_suggestion`；与人工标签严格分列 |
| 自动评审（机器） | `artifacts/b_eval/qa_auto_review.json`、`qa_human_score.json → auto_review / machine_metrics` | 机器判定，**不得**与人工指标合并 |
| 评估口径 | `docs/B_QA_GOLD_STANDARD_REPORT.md`（§16 判定标准、§20 直接回答原则、§21 最终人工指标）、`docs/B_QA_CONTESTED_CRITERIA.md`（争议口径提案）、`docs/B_REFUSAL_RULES.md`（拒答规则） | 宽口径/严格口径、排除项、`not_applicable` 与空值/`unknown` 的区别 |
| 性能口径 | `docs/B_QA_PERFORMANCE_REPORT.md` | 计时范围、超时阈值、两批不合并的说明、75/90/95 逐指标对照 |

**指标分列提示**：`qa_human_score.json` 顶层的 `answer/citation/refusal` 是**人工指标**；
`machine_metrics` 与 `auto_review` 是**机器指标**（引用命中率、词命中率、拒答一致率、引用可追溯率）。
两类口径不同（例如前者要求"引用支持结论"，后者只看"命中文档"），不可合并或互相替代。
另有历史机器口径记录在 `docs/B_BASIC_METRICS_ACCEPTANCE.md`。

## 4. 资产处置建议（策略感知）

| 环节 | 权威产物 | 关键字段 / 口径 |
| --- | --- | --- |
| 策略输入 | `config/asset_policies.example.json`、`config/assets.example.json` | 六字段：`asset_id / maintenance_window / business_importance / prohibited_actions / owner / acceptable_downtime_minutes`（示例为**合成数据**，`synthetic: true`） |
| 生成与约束 | `tools/asset_disposal_advisor.py` | 策略校验、优先级五分量、约束检查（禁止动作/窗口/停机/冲突）、保守默认（无策略＝停机 0、破坏性动作全禁） |
| 演示结果 | `artifacts/b_eval/asset_disposal_demo.json`、`asset_disposal_file_input.json` | `assets[].findings[].{link_status,priority,recommended_actions,blocked_actions,scheduling,conflicts,evidence_ids,needs_human_review}` |
| 测试 | `tests/test_b_asset_disposal_advisor.py` | 覆盖 12 个验收场景（含缺失策略、禁止动作、停机冲突、证据不足） |
| 报告 | `docs/B_ASSET_DISPOSAL_REPORT.md`、`docs/B_ASSET_POLICY_READINESS.md` | 流程、权重、约束、演示三案例、遗留项；命名口径为"策略感知处置建议" |

## 5. 演示证据

| 环节 | 权威产物 | 关键字段 / 口径 |
| --- | --- | --- |
| 一键复现 | `tools/run_b_demo_evidence.py` → `artifacts/b_eval/demo_evidence.json` | `results[]`：`scenario_id / run_id / question / answer / refused / citations[].{chunk_id,document_id,char_start,char_end} / duration_ms / mode` |
| 截图 | `docs/screenshots/b-qa-00-workbench.png`（真实应用 UI 首页）<br>`b-qa-01-basic.png`、`b-qa-02-multiturn.png`、`b-qa-03-crossdoc.png`、`b-qa-04-refusal.png`、`b-qa-05-citation.png` | 后 5 张为**真实运行结果的证据渲染页**（非交互会话录屏），每张标注 run_id 与引用清单 |
| 截图清单 | `artifacts/b_eval/b_demo_screenshots.json` | `shots[]`：`kind / scenario / run_id / question / citation_count / citations[] / file` |
| 截图工具 | `tools/render_b_demo_screenshots.py` | 用已安装的 Microsoft Edge headless 截图（本项目 venv 无 playwright）；A 任务工具 `tools/capture_operations_screenshots.py` 未改动 |
| 报告 | `docs/B_DEMO_EVIDENCE_REPORT.md` | 五场景结果表、诚实声明、引用可核验性、截图清单与性质说明 |

## 6. 已知缺口（事实陈述）

1. **POC 状态、资产关联两个维度无数据**：交付语料（`D:\ICT\intel-data-b\intel.sqlite`，2026-10-12 只读复核）
   `events` 93 条中含 `poc[]` 的 0 条，`assets` / `assessments` 表无记录，因此这两个维度没有可计算的分母。
   **记"无数据"，不记 0**——0 分与"没有分母"是两种含义。来源、可补性与报告写法见
   `docs/B_DIMENSION_SCOPE_POC_ASSET.md`。
2. **关系 recall / F1 不可计算**：缺"应抽取而未抽取"的金标准全集，`relation_score_all.json → fn_source.available = false`。
3. **多跳/跨文档能力受限**：见 `multihop_path_validation.json → counts.by_chain_type` 与 `missing_edge_summary`；31 条题**人工核验状态**见题集内 `annotation`（未核验则不计入任何指标）。
4. **资产维度没有真实资产源**：交付语料 `assets` / `assessments` 无记录；可用的只有合成 BOM
   （`config/assets.example.json`，`synthetic=true` / `is_demo=true`）与本机依赖清单，均非企业资产源。
   `asset_disposal_demo.json` 中 `asset.synthetic = true`，因此表述为"策略感知处置建议"，非个性化推荐。
   判定口径见 `docs/B_DIMENSION_SCOPE_POC_ASSET.md`。
5. **问答人工指标的分母构成**：见 `qa_human_score.json` 各字段与 `docs/B_QA_GOLD_STANDARD_REPORT.md` §21（含 `not_applicable`、空值、`unknown` 的处理说明）。

## 7. 复现命令

```powershell
# 关系评测：回灌 → 评分
.\.venv\Scripts\python.exe tools\apply_b_relation_labels.py `
    --worksheet artifacts\b_eval\relation_annotation_worksheet_v2.csv `
    --out artifacts\b_eval\relation_candidates_labeled_all.json
.\.venv\Scripts\python.exe tools\score_b_relation_annotations.py `
    --input artifacts\b_eval\relation_candidates_labeled_all.json `
    --out artifacts\b_eval\relation_score_all.json

# 问答评测：再跑一批 → 跨批次统计 → 人工指标
.\.venv\Scripts\python.exe tools\run_b_qa_eval.py --out artifacts\b_eval\formal_qa_performance_run2.json
.\.venv\Scripts\python.exe tools\build_b_qa_performance_report.py `
    --run A=artifacts/b_eval/formal_qa_results.json `
    --run B=artifacts/b_eval/formal_qa_performance_run2.json `
    --out artifacts/b_eval/qa_performance_stats.json
.\.venv\Scripts\python.exe tools\score_b_qa_annotations.py --out artifacts\b_eval\qa_human_score.json

# 演示证据与截图
.\.venv\Scripts\python.exe tools\run_b_demo_evidence.py --out artifacts\b_eval\demo_evidence.json
.\.venv\Scripts\python.exe tools\render_b_demo_screenshots.py --base http://127.0.0.1:8010/

# 资产处置建议（合成资产 + 真实事件）
.\.venv\Scripts\python.exe tools\asset_disposal_advisor.py --demo --out artifacts\b_eval\asset_disposal_demo.json

# 相关测试
.\.venv\Scripts\python.exe -m pytest tests -q -p no:cacheprovider -rsx
```

## 9. 重评测批次（2026-10-02，RAG 链路修改后）

**背景**：`8db19cf` 修改了 `app/rag.py`（检索短语约束 + 抽取式答案）并新增
`app/b_evaluation.py`，旧人工基线描述的是改造前的回答，因此另建一批文件重跑；
旧文件全部保留，不覆盖。

| 环节 | 权威产物（新批次） | 关键字段 / 口径 |
| --- | --- | --- |
| 机器评测 | `artifacts/b_eval/formal_qa_results_20261002.json` | `records[]`、`totals.{document_hit,term_hit,refusal_accuracy,citations}`、`latency_ms.{p50,p95}`、`totals.{timeouts,errors}` |
| 性能统计（分批） | `artifacts/b_eval/qa_performance_20261002.json` | `batches[]`（A_prev / B_prev / C_20261002 三批独立分位数）、`comparison.per_question[]`（仅同题号集合时逐题差值） |
| 自动评审 | `artifacts/b_eval/qa_auto_review_20261002.json` | 规则判定，与人工指标分列；不得当准确率 |
| 拒答分类 | `artifacts/b_eval/refusal_failure_classification_20261002.json` | `counts.{correctly_refused,wrongly_answered}`（本批次已修正计数口径）、`cases[].failure_category` |
| 机器辅助裁定（B 类） | `artifacts/b_eval/qa_machine_adjudication_20261002.{json,csv}` | `cases[].{answer_correctness,citation_support,refusal_correctness}.{suggestion,status,confidence}`；`summary.tier_C_human_confirmed_gold` |
| 候选标准答案 | `artifacts/b_eval/qa_candidate_answers_20261002.json` | 机器候选，**不是**金标准 |
| 人工确认工作表 | `artifacts/b_eval/qa_final_confirmation_worksheet_20261002.csv` | 人工三列 + `人工核验人/时间/备注`，当前全空 |
| 人工指标 | `artifacts/b_eval/qa_human_score_20261002.json` | 人工确认 50/50（署名 `人工复核-用户确认`，2026-10-04）；本文件是重评测批次的人工指标，**不替代**旧的 `qa_human_score.json` |
| 关系候选（新库） | `evaluation/b_relation_candidates_20261002.json` | 未含 POC 数据源时的基线；`poc`、`asset_assessment` 无候选 |
| 关系候选（含 POC） | `evaluation/b_relation_candidates_20261002_poc.json` | 153 条；`poc` 32 条（16 个事件）；`asset_assessment` 仍无候选 |
| POC 前置探测 | `artifacts/b_eval/nvd_poc_backfill_20261002.json` | 既有快照与本库不同源的真实输出：`events_updated` 为 0 |
| POC 定向回填 | `artifacts/b_eval/nvd_poc_backfill_cve_scope_20261002.json` | 按库内 37 个 CVE 拉取 NVD 后在**库副本**上回填：`events_updated` 16 |
| POC 快照清单 | `artifacts/b_eval/nvd_poc_snapshot_manifest_20261002.json` | 每个 CVE 的文件 SHA256、公开引用数、Exploit 标签数；含原库/副本 SHA256 |
| 页面一致性核对 | `artifacts/b_eval/scorecard_consistency_20261002.json` | `checks[]`（页面口径 vs 冻结 JSON 逐字段）、`mismatches[]`、`conclusion.page_shows_new_batch` |
| 阶段报告 | `docs/B_REEVAL_20261002_REPORT.md` | 本轮方法、真实数值、缺口、复现命令 |
| 回归测试 | `tests/test_b_reeval_20261002.py` | 新批次 50 题、旧文件保留、批次不混算、C 类人工=0、空值不进分母、拒答计数自洽、页面一致性 |

**本批次缺口（如实记录）**：

* 人工金标准：新回答的人工核验尚未完成，因此人工答案/引用/拒答指标**暂不可计算**。
* `poc` 维度：交付语料 `events[].poc[]` 全空；库外 NVD 快照与本库不同源
  （`nvd_poc_backfill_20261002.json` 实测 `events_updated = 0`），只有按库内 CVE 定向抓取后
  回填副本才有数据（`nvd_poc_backfill_cve_scope_20261002.json`：16 个事件）。口径见
  `docs/B_DIMENSION_SCOPE_POC_ASSET.md`。
* 跨文档路径：语料内论文无互引、论文正文 CVE 与库内 CVE 无交集，0/21 无法在不造假的
  前提下提升，需新增来源。
* 共享问答主链路回归**已关闭（2026-10-12）**：`tests/test_rag_mixed_language_query.py` 的中频词用例
  已随 `9ff7383` 修复转绿（该模块 30 passed）。根因不是 `len(chunks) // 10` 阈值——`kernel-level`
  （df 9.0%）本来就通过守卫，失败的是 `multi-agent` 那条，且输在排序：中文短语的同义词组
  （`论文` → `paper / study / arxiv`）原先被逐词独立计分，把真正讨论 `multi-agent` 的论文挤出前 8；
  现改为按一个概念取最强成员计分。

## 10. 重评测确认批次（2026-10-12，A1 排序修改后）

**背景**：`9ff7383` 改了 `app/rag.py` 的同义词组计分（中文短语按一个概念取最强成员），
问答的引用集合随之变化。用同一份交付语料重跑，并做了 A1 前后的对照。

| 环节 | 权威产物（新批次） | 关键字段 / 口径 |
| --- | --- | --- |
| 问答机器评测 | `artifacts/b_eval/formal_qa_results_20261012.json` | 与 `formal_qa_results_20261002.json` 同结构；50 题，`records[]`、`totals.*`、`latency_ms.*` |
| 关系评测 | 无需新批次 | 重跑 `relation_score_gold_20261010.json` 与冻结对照 `relation_score_gold_frozen20261006_20261010.json`，均与已交付文件**逐字节相同**，无漂移 |
| 阶段报告 | `docs/B_REEVAL_20261012_REPORT.md` | 对照方法、逐题差异（BQA-002 / 003 / 005 / 034）、原因归属、未刷新的下游产物清单 |

**仅问答机器指标变化**：引用命中 0.8889 → **0.9722**，预期词命中 0.8158 → **0.9211**，
拒答一致率 0.84 不变，引用总数 217 → 222。A1 之前的代码（`b020090`）在同一语料上
**逐项复现**了 0.8889 / 0.8158 / 0.84 / 217，因此差异可确定性归因于 A1，而非机器或语料差异。

**边界**：09-30 基线的 `formal_qa_results.json` 未改动；由它派生的
`qa_auto_review*` / `qa_candidate_answers*` / 复核工作包 / 拒答分类 / 性能统计等产物本批次**未重跑**，
口径仍是 09-30 基线。是否整体刷新到 10-12 批次（涉及人工标签是否重签）由队长决定。

## 8. 维护约定

* 指标数值只在第 1–3 节列出的**权威文件**中维护；本索引只维护"路径 + 口径说明 + 缺口"。
* 改动产物路径或新增产物时，更新本文件对应行的路径，不在此处复制数值。
* 本文件用于替代此前的 `docs/B_COMPLETION_CHECKLIST.md`（自评式清单，已移除），以避免同一数字在多份文档中重复维护。
