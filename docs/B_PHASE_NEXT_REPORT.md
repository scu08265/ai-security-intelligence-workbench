# B 任务 · 阶段收口与下一步

| 项 | 值 |
| --- | --- |
| 日期 | 2026-09-30 |
| 分支 | `feat/b-evaluation`（未切换，未暂存，未提交） |
| 真实数据库 | 8,183,808 B / `4095a5b1ff836f70baf5552304aac95f` —— **本轮零写入，前后一致** |

## 1. 本轮实际修改

| 文件 | 变更 | 原因 |
| --- | --- | --- |
| `app/rag.py` | 修改（+42 / −8） | D-1 区间校验用原文；D-2 区分度阈值；**N-1** 词元尾随标点剥离；**N-2** 阈值由 N/20 放宽到 N/10 |
| `app/intelligence.py` | 修改（+16） | D-4 答案与引用语义一致（上一轮已实施，本轮复核通过） |
| `app/evaluation.py` | 修改（2 行） | 更早轮次的闭包绑定修复 |

新增（全部为 B 任务自有文件）：

| 类型 | 文件 |
| --- | --- |
| 数据集 | `evaluation/b_formal_qa_set.json`（50 题）、`evaluation/b_multihop_candidates.json`（31 条）、`evaluation/b_relation_candidates.json`（121 条） |
| 工具 | `tools/run_b_qa_eval.py`、`tools/build_b_multihop_candidates.py`、`tools/build_b_relation_candidates.py`、`tools/score_b_relation_annotations.py`、`tools/run_b_demo_evidence.py`、`tools/run_paper_fulltext.py` |
| 测试 | `test_rag_answer_grounding_edges.py`(17)、`test_b_formal_qa_set.py`(13)、`test_b_multihop_candidates.py`(8)、以及此前 6 个 B 测试文件 |
| 报告 | `docs/B_FORMAL_QA_EVAL.md`、`B_MULTIHOP_DATASET_REPORT.md`、`B_RELATION_ANNOTATION_REPORT.md`、`B_ASSET_POLICY_READINESS.md`、`B_DEMO_EVIDENCE_REPORT.md`、本文件 |
| 运行产物 | `artifacts/b_eval/*.json`（评测结果、修复前对照、关系统计、演示证据） |

**未修改**：`app/agents.py`、`app/collectors/`、`app/reliability.py`、`app/scheduled_job.py`、
`app/self_healing.py`、`app/multi_agent_runtime.py`、`scripts/`、`.github/`、`reports/`（git 核对为空）；**schema 未动**。

## 2. 测试结果（实测）

| 范围 | 结果 |
| --- | --- |
| B 任务 9 个测试文件 | **145 passed** |
| 全量 `pytest -q` | **423 passed**，0 failed，0 skipped（上一轮基线 373） |

## 3. 完成度总表

| 目标 | 状态 | 实测依据 |
| --- | --- | --- |
| ≥100 条人工核验富化关系 + TP/FP/FN | **0%**（候选已备好） | 候选 121 条，人工核验 0 条，`computable=false` |
| ≥30 道真实多跳题 | **部分完成** | 31 条**候选**题，0 条人工验收；系统无多跳能力 |
| 50–100 题问答集 + 全套指标 | **部分完成** | 50 题已建并跑通；**语义准确率未评测** |
| 策略感知资产处置建议 | **未就绪** | 资产 0 条；4 个策略字段不存在 |
| 演示证据 | **部分完成** | 5 场景真实运行；无截图；DEMO-02 为部分失败 |
| 检索/引用质量 | **显著提升** | 引用命中 75.0%→86.1%；引用可追溯 187/187 |

## 4. 被阻塞项与原因

| # | 阻塞项 | 原因 | 需要什么 |
| --- | --- | --- | --- |
| 1 | 语义答案准确率 | 无人工核验标准答案 | **人工标注者** |
| 2 | 100 条关系核验 | 同上 | 人工标注者 + 标注指南（已给出） |
| 3 | 真实多跳 | 无实体/关系抽取、关系谓词单一 | 新能力开发 + 可能改 schema |
| 4 | 多轮追问（RAG 侧） | RAG 路径不继承会话上下文 | 改共享问答流程，**需单独授权** |
| 5 | 跨文档综合 | 答案生成只拼原文，无综合步骤 | 启用 `generator` 或新增综合步骤，**需单独授权** |
| 6 | 策略感知建议 | 资产 0 条 + 4 字段缺失 | 资产数据 + schema 变更授权（须与 A 任务协调） |
| 7 | 页面截图 | 环境无法截图 | 有图形界面的环境 |
| 8 | POC 维度 | 无 POC 采集器 | 新数据源或明确标注"不可评测" |

## 5. 下一步（按优先级）

1. **人工核验**（最高优先，解锁 1、2）：按 `B_RELATION_ANNOTATION_REPORT.md` 第 6 节填写标注。
2. **单独授权项**：RAG 多轮上下文、跨文档综合、资产策略 schema —— 三者都需要改共享模块或 schema。
3. **多跳能力**：先积累 `verified: true` 的关系边，再谈路径搜索（`B_MULTIHOP_DATASET_REPORT.md` 第 5 节）。
4. **补 POC 数据源**，否则该维度永久为 0。

## 6. 未确认事项（汇总）

- 引用内容是否支持结论 —— 未人工核验
- 50 题与 13 条冒烟题的答案质量 —— 均为任务执行者编写，非人工金标准
- `two_hop` 候选题中"论文是否真的讨论该事件" —— 未确认
- 22 个文档内容质量 —— 未逐个人工抽读
- 未测试 `/api/chat` 的 HTTP 层（直接调用 `agents.answer`）
- 旋转文本 / `fontTools` 缺失对抽取文本的影响 —— 未量化

---

# 更新 · 关系评测闭环、多跳路径验证与拒答复核（2026-09-30）

> 上一节（1–6）保持原样未改动。本节记录本轮新增成果。

## 1. 本轮改动文件

| 文件 | 类型 | 理由 |
| --- | --- | --- |
| `tools/auto_review_relations.py` | 修改 | 新增 **OSV 结构化语义核验**（`R-FV-STRUCTURED` / `R-VR-STRUCTURED` / `R-VR-VERSIONS`），不再只靠字符串出现；快照未命中改判 `unavailable` |
| `tools/score_b_relation_annotations.py` | 修改 | 补 **F1**；`prediction.verdict` 缺省视为 `present` 并记录；**recall/F1 需外部金标准才可算**（新增 `--gold`） |
| `tools/build_b_review_workpackets.py` | 修改 | 新增第三份产物：**含自动核验结论的人工复核表 v2** |
| `tools/multihop_path_retriever.py` | **新增** | 最小结构化路径检索器 + 验证器（受限 BFS，只走有证据的边） |
| `tools/classify_b_refusals.py` | **新增** | 拒答失败分类（只读） |
| `tests/test_b_multihop_path.py` | **新增** | 12 项路径检索/验证测试 |
| `tests/test_b_review_workpackets.py` | 修改 | 适配评分器新语义并**加强**断言（F1、gold、默认预测、v2 复核表） |
| `artifacts/b_eval/relation_final_review_worksheet.csv` | **新增** | 121 行，含自动判定与理由 |
| `artifacts/b_eval/multihop_path_validation.json` | **新增** | 31 条候选题的路径验证结果 |
| `artifacts/b_eval/refusal_failure_classification.json` | **新增** | 12 条应拒答题的分类 |

**未修改**：`app/` 下任何代码、数据库 schema、共享问答流程、A 任务模块。

## 2. 测试结果（实测）

| 范围 | 结果 |
| --- | --- |
| `pytest tests\test_b_multihop_path.py ...`（5 个 B 测试文件） | **63 passed** |
| **全量 `pytest -q -p no:cacheprovider -rsx`** | **468 passed，0 failed，0 skipped / 138.89 s**（上一轮 451，+17） |

## 3. 关系评测：TP/FP/FN/P/R/F1 能否计算

### 3.1 标注口径（本轮固定）

| 概念 | 定义 |
| --- | --- |
| 标注单位 | **一条候选关系**（`relation_id`），不是文档、也不是字符串 |
| 正例 `positive` | 人工对照来源原文，确认该关系成立 |
| 负例 `negative` | 人工对照来源原文，确认该关系**不**成立 |
| 证据充分 | 原始来源（快照/结构字段）能直接支撑候选值 |
| 证据不足 | `unknown` / 无快照 / 非可解析形式 → **单列，不入分母** |
| 无法判定 | `not_applicable`，或 `status != human_verified` |

### 3.2 自动核验（121 条）

| 判定 | 条数 |
| --- | ---: |
| supported | **63** |
| contradicted | **0** |
| insufficient_evidence | **58** |

本轮新增的**结构化**核验让 `fixed_version` 不再依赖字符串：
`R-FV-STRUCTURED` 直接把候选与 OSV 快照的 `affected[].ranges[].events[].fixed` 比对，
**12/12 精确一致**；`version_range` 有 **12 条**通过区间还原（`introduced/fixed` → `< X`）
且 `R-VR-VERSIONS` 确认 OSV 列出的全部受影响版本都落在候选区间内。

### 3.3 结论：**目前仍不可计算，但流程已就绪**

| 指标 | 状态 | 原因 |
| --- | --- | --- |
| **Precision** | 标注后可计算 | `TP/(TP+FP)`；缺省预测 `present`，已记录假设 |
| **Recall** | **不可计算** | 候选集**本身就是系统输出**，没有"应抽取但未抽取"的金标准清单，FN 无来源 |
| **F1** | **不可计算** | 依赖 recall |
| TP / FP | 标注后可计算 | 需要人工 `positive` / `negative` 标签 |
| FN | **不可计算** | 同上 |

脚本已支持 `--gold`（`{"expected_relation_ids": {ID: 维度}}`）后即可算出 recall/F1，
并有 4 项测试覆盖（含 `precision=0 & recall=0` 时 F1 返回 `null` 而非 0）。

**人工核验数量：0 条。** 因此 `relation_score.json` 仍为 `computable: false`。

### 3.4 POC 与资产关联：确认无法合法构建候选

| 维度 | 本地数据实况 | 结论 |
| --- | --- | --- |
| POC | 93 个事件的 `poc` 字段**共 0 条**；179 条 `references` 中匹配 `exploit/poc/nuclei/…` 的 **0 条** | **无证据，不建候选**；需新增 POC 数据源 |
| 资产关联 | 资产 **0 条**、研判 **0 条** | **无证据，不建候选**；需资产数据 + 策略字段授权 |

## 4. 多跳：候选数量、可复现数量与路径验证

### 4.1 最小闭环已跑通

新增 `tools/multihop_path_retriever.py`：从本地真实数据建图（**只有两类边**，
每条边都带 `chunk_id` 或事件字段作为证据），然后在图上做受限 BFS（≤4 跳）。

| 项 | 结果 |
| --- | ---: |
| 图规模 | 160 节点 / 121 条边 |
| 边类型 | `component_is`（事件→组件）、`mentioned_in`（组件→文档） |
| 候选题总数 | 31 |
| **找到真实路径** | **10**（全部为 `two_hop`） |
| 不连通 | 21（全部为 `cross_document`） |

### 4.2 两类题的结论（如实区分）

| 类型 | 数量 | 路径验证 | 说明 |
| --- | ---: | --- | --- |
| `two_hop`（事件→组件→文档） | 10 | **10/10 连通**，每跳有证据 ID | 这是**可复现、可追溯**的结构化路径 |
| `cross_document`（术语→文档A→文档B） | 21 | **0/21 连通** | 图中**没有文档到文档的边**；验证器如实报"不连通"，**不补虚构边** |

**可复现的多跳闭环数量 = 10 条**（不是 31 条）。跨文档题缺边属**数据缺口**，
需要通过关系抽取或人工标注关系边来补齐。

### 4.3 路径输出格式

`artifacts/b_eval/multihop_path_validation.json` 每题给出
`path_found` / `hops` / `path_nodes` / `path_edges[{from,to,relation}]` /
`evidence_ids` / `matches_declared_path` / `failure_reason`。

## 5. 拒答失败分类（12 条应拒答题）

新增 `tools/classify_b_refusals.py`（只读复现），产物
`artifacts/b_eval/refusal_failure_classification.json`。

| 分类 | 条数 | 可复现样本 |
| --- | ---: | --- |
| `correct_refusal`（正确拒答） | 6 | 全部 6 条确实拒答 |
| `candidate_multihop_answered_topically` | 2 | BQA-039 / BQA-040：返回主题相关引用，无推理链 |
| `generic_word_answered_from_event_index` | 2 | BQA-046 `vulnerability`、BQA-050 `security` → 事件索引按标题匹配后正常作答 |
| `numeric_token_false_positive` | 1 | BQA-044 `2027 年世界杯冠军是谁？` → 数字串 `2027` 在 2 份文档中出现 |
| `synthesis_request_answered_with_quotes` | 1 | BQA-047 要求综述全部文档 → 返回 6 条引用而非综述 |

**评审规则是否有误判：无。** 4 条 `contradicted` 与人工口径一致（确实应拒答）。
其中 **2 条**（BQA-046/050）涉及 **`should_refuse` 口径分歧**——
单通用词是否算"证据不足"需要人工裁定，已标 `needs_human_review = true`。

**最小修复建议**（均未实施，未改问答主流程）：

| 分类 | 建议 |
| --- | --- |
| numeric_token_false_positive | 把纯数字/年份词元降权或剔除 |
| synthesis_request_answered_with_quotes | 识别综述类请求并回复能力边界 |
| candidate_multihop_answered_topically | 标注能力边界（需真正的路径检索才可能作答） |
| generic_word_answered_from_event_index | 先由人工明确 `should_refuse` 口径 |

## 6. 数据库前后核验

| 项 | 开始前 | 结束后 | 结论 |
| --- | --- | --- | --- |
| 大小 | 8,183,808 B | **8,183,808 B** | 未变 |
| SHA-256（前 32） | `4095a5b1…8254285` | **`4095a5b1…8254285`** | 未变 |
| schema | — | 未改动 | 未变 |

所有评测均在**临时副本**上执行；`app/rag.py` 的读取只走只读连接。

## 7. Git 工作区状态（仅检查）

| 项 | 状态 |
| --- | --- |
| 分支 | `feat/b-evaluation`（未切换） |
| 暂存区 | **空** |
| Git 写操作 | **无** |
| 已跟踪改动 | `app/evaluation.py`、`app/intelligence.py`、`app/rag.py`（均为**上一轮之前**的改动，本轮未再修改） |
| 禁改文件 | 全部未改动 |
| 未跟踪 | 既有 B 产物与报告 + 本轮新增 5 个文件 |

## 8. B 任务完成情况

### 已完成
- RAG 语料与检索修复（D-1/D-2/D-4 + N-1/N-2），全量回归 468 passed
- 固定 50 题问答评测集 + 逐题自动评审 + 混淆矩阵
- 121 条关系候选 + **结构化**自动核验 + 三份人工复核工作包
- **10 条可复现的多跳结构化路径**（含验证器与 12 项测试）
- 拒答失败分类（12 条，5 类）
- 5 个演示场景真实运行记录

### 部分完成
- 关系评测：**口径与工具就绪，标注为 0 条** → P/R/F1 不可计算
- 问答评测：题集与机械指标完成，**语义准确率缺人工核验**
- 多跳：10 条闭环可复现；其余 21 条因缺边无法验证
- 演示证据：运行记录完整，**截图缺失**（环境无浏览器自动化）

### 未完成
- 100 条人工核验关系 + TP/FP/FN/P/R/F1
- 真正跨文档综合（需文档间关系或综合步骤，属共享流程改动）
- POC 维度（无数据源）
- 策略感知资产处置建议（资产 0 条 + 4 个策略字段缺失）

## 9. 下一步最重要的 3 项工作

1. **人工标注 121 条关系候选**（至少先做 `fixed_version` 12 条 + `cvss` 22 条）
   —— 之后 precision 立即可算；若能同时给出"应抽取全集"，recall/F1 也可算。
2. **补齐文档间关系边**（关系抽取或人工标注），把可复现多跳闭环从 10 条推向 30 条。
3. **人工裁定 `should_refuse` 口径**（BQA-046/050 这类单通用词题），
   否则拒答召回率 50% 这个数字无法解释清楚。

---

# 更新 · 交付材料整理（2026-09-30 第二轮）

## 1. 本轮修改文件与新增产物

| 文件 | 类型 | 说明 |
| --- | --- | --- |
| `tools/apply_b_relation_labels.py` | **新增** | **补上关键缺口**：把人工填写的 CSV 回灌成评分脚本可读的 JSON |
| `tools/build_b_review_workpackets.py` | 修改 | 新增第四份产物：可交付的人工标注表（含优先级与证据 ID） |
| `tools/multihop_path_retriever.py` | 修改 | 新增**缺失关系清单**（逐跳说明缺哪类边、需要什么证据） |
| `tests/test_b_annotation_pipeline.py` | **新增** | 16 项标注流水线测试 |
| `docs/B_RELATION_ANNOTATION_REPORT.md` | 更新 | 追加"人工标注指南"（标签定义、优先级、命令、纪律） |
| `docs/B_REFUSAL_RULES.md` | **新增** | 拒答可执行规则 R1–R5 + 逐题记录 + 争议与失败区分 |
| `docs/B_DEMO_EVIDENCE_REPORT.md` | 更新 | 追加统一演示清单与复现命令 |
| `artifacts/b_eval/relation_annotation_worksheet_v2.csv` | **新增** | 121 行，按优先级排序，含自动结论与证据 ID |
| `artifacts/b_eval/relation_candidates_labeled.json` | **新增** | 回灌产物（当前 0 条标签，全部空白） |
| `artifacts/b_eval/multihop_path_validation.json` | 更新 | 增加 `missing_edges` 与缺失汇总 |

**未修改**：`app/` 下任何代码、数据库 schema、共享问答主流程、其他成员模块。

## 2. 关系标注工作流能否直接投入人工使用

**可以。** 端到端链路已实测跑通（用临时副本模拟标注，真实表保持空白）：

```
relation_annotation_worksheet_v2.csv（121 行，已排序）
  → tools/apply_b_relation_labels.py   （CSV → JSON，拒绝非法/重复/未知 ID）
  → artifacts/b_eval/relation_candidates_labeled.json
  → tools/score_b_relation_annotations.py（TP/FP/FN/Precision，必要时 Recall/F1）
```

模拟验证结果（12 条标签：9 positive + 3 negative）：
`computable: true`、`TP=9`、`FP=3`、**`precision=0.75`**、
`recall`/`f1` 为 `null` 并附原因（缺"应抽取全集"）。

**本轮之前这条链路是断的**（人工填 CSV，评分器读 JSON），现已打通。

## 3. 当前真实人工标注数量与可计算指标

| 项 | 数量 |
| --- | ---: |
| 关系候选 | 121 |
| **已人工标注** | **0** |
| 待标注 | 121 |
| 可用指标 | **无**（`relation_score.json` 仍 `computable: false`） |
| 标注后立即可算 | `Precision`（precise 到维度与微/宏平均） |
| 仍需额外金标准 | `Recall`、`F1`、`FN` |

## 4. 拒答规则与争议样本处理

新增 `docs/B_REFUSAL_RULES.md`，明确 R1–R5 五条规则，并逐题记录
BQA-039/040/044/046/047/050 的预期行为、证据、实际行为、失败类型。

**关键区分**：

| 性质 | 条数 | 题目 |
| --- | ---: | --- |
| 正确拒答 | 6 | 其余 6 道 |
| **口径争议（需人工裁定）** | 2 | BQA-046、BQA-050（单通用词是否算证据不足） |
| **系统真实失败** | 4 | BQA-044、047、039、040 |

因此 `拒答召回率 50%` 应拆读为 **真实失败 4 条（33.3%）+ 口径争议 2 条（16.7%）**。
本轮**未修改共享问答主流程**，只交付规则与分类。

## 5. 多跳缺失关系清单与演示材料完整性

### 5.1 多跳

| 类型 | 数量 | 结果 |
| --- | ---: | --- |
| `two_hop` | 10 | **10/10 连通**，节点/边/证据 ID 齐全 |
| `cross_document` | 21 | 0/21 连通 |

缺失清单（`multihop_path_validation.json::missing_edge_summary`）：

| 需要的边类型 | 出现次数 | 含义 |
| --- | ---: | --- |
| `term_node_with_evidence` | 21 | 术语（如 `AUROC`）不是图里的已登记实体节点 |
| `document_to_document` | 126 | 两篇文档之间没有带证据的关系边 |

**清单只说明缺什么，不含任何补造的关系。**

### 5.2 演示材料

5 个场景的清单已补齐（目标/输入/预期/运行 ID/引用数/结果/截图状态/复现命令），
见 `docs/B_DEMO_EVIDENCE_REPORT.md`。**截图不可用**：无 playwright / selenium /
浏览器缓存 / PATH 上的浏览器；按边界不安装大型依赖。

### 5.3 资产处置建议

仅整理策略输入模板、字段说明与数据缺口（`docs/B_ASSET_POLICY_READINESS.md`）。
**未伪造任何资产记录，未修改 schema。**

## 6. 测试结果

| 范围 | 结果 |
| --- | --- |
| 本轮相关 4 个测试文件 | **61 passed** |
| **全量 `pytest -q -p no:cacheprovider -rsx`** | **484 passed，0 failed，0 skipped / 143.63 s**（上一轮 468，+16） |

## 7. 数据库前后核验

| 项 | 开始前 | 结束后 |
| --- | --- | --- |
| 大小 | 8,183,808 B | **8,183,808 B（未变）** |
| SHA-256 | `4095a5b1…8254285` | **`4095a5b1…8254285`（未变）** |

## 8. Git 工作区状态（仅检查）

分支 `feat/b-evaluation`（未切换）；**暂存区空**；**无任何 Git 写操作**；
禁改文件 git 核对为空；已跟踪改动仍为早前那 3 个 `app/` 文件，**本轮未再修改 `app/`**。

## 9. 下一步仍需人工完成的事项

1. **填写 `artifacts/b_eval/relation_annotation_worksheet_v2.csv`**
   （建议从第 1 行往下：`fixed_version` 12 条 → `cvss` 22 条），
   然后依次运行 `apply_b_relation_labels.py` 与 `score_b_relation_annotations.py`。
2. **填写 `artifacts/b_eval/qa_review_worksheet.csv`** 的人工判定列
   （`high` 优先级 36 题）。
3. **裁定 BQA-046 / BQA-050 的 `should_refuse` 口径**（单通用词是否算证据不足）。
4. 如需 Recall/F1：额外提供"应抽取关系全集"的 `--gold` 文件。
