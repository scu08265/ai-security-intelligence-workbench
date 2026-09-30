# B 任务：问答人工金标准阶段报告

本报告记录 50 题问答评测的人工金标准建设工作：新增的金标准工作表、批量复核材料、
人工与自动分离的指标口径，以及当前**尚不可计算**的部分。

**核心结论（先说清楚）**：截至本轮结束，**人工金标准判定数为 0**，
因此答案准确率、引用准确率、拒答准确率/召回率等**人工指标一律不可计算**；
已实际测得的只有机器指标（引用命中、词命中、引用可追溯、拒答一致率、时延），
以及自动评审判定（单独列出）。不把自动结果冒充人工结论。

---

## 一、本轮产出文件

| 文件 | 内容 |
| --- | --- |
| `artifacts/b_eval/qa_gold_standard_worksheet.csv` | **50 题**人工金标准工作表（37 列），人工列全部留空 |
| `artifacts/b_eval/qa_gold_evidence_packet.md` | **50 题**证据包：系统答案、逐条引用原文、语料只读探测、自动规则明细、待确认问题 |
| `artifacts/b_eval/qa_candidate_answers.json` | **机器候选标准答案**（引用原文抽取 / 拒答建议），逐条标注 `suggestion_level=machine_candidate` |
| `artifacts/b_eval/qa_adjudication_table.csv` | **统一裁定表**（50 行），争议题排最前，含建议标签/理由/可选判定及后果/最小判断 + 3 列可填判定 |
| `tools/score_b_qa_annotations.py` | 人工指标计算工具（人工与自动严格分离），支持 `--out` 输出 JSON |
| `tools/build_b_qa_candidate_answers.py` | 生成机器候选标准答案与统一裁定表 |
| `tools/apply_b_qa_labels.py` | 把裁定表的判定**一键回填**到金标准工作表（非法值/重复 ID/缺署名一律中止） |
| `artifacts/b_eval/qa_human_score.json` | 首次运行结果（当前 `computable: false`，原因见第五节） |
| 本文件 | 阶段报告 + 批量复核材料 |

**三个层次严格分开**：`machine_candidate`（机器候选标准答案，本报告与上述文件产出）→
`auto_review`（自动评审规则判定，`qa_auto_review.json`）→ `human_gold`（人工确认，
**当前 0 条**）。任何一层都不得写入另一层的字段。

既有 36 题产物（`evidence_packet_qa.md`、`evidence_qa_label_sheet.csv`）**未被覆盖**。

## 二、50 题现状盘点（机器实测，非人工结论）

| 项目 | 数值 |
| --- | --- |
| 题目总数 | 50（基础事实问答 10、术语及语义查询 8、跨文档问答 8、中英文混合查询 6、多轮追问 6、无证据/范围外 5、拒答及证据不足 5、真实多跳问答 2） |
| 应作答 / 应拒答 | 38 / 12 |
| 系统实际作答 / 拒答 | 39 / 11 |
| 带引用（可逐条核对原文）的题 | 35 题（共 187 条引用，**可追溯率 187/187 = 100%**） |
| 无任何引用的题 | 15 题（拒答题 + 6 道多轮追问 + BQA-008/027 事件路径题） |
| 引用命中率 | 31/36 = 86.11%（仅表示预期 document_key 被引用命中） |
| 预期词逐字命中率 | 25/38 = 65.79%（**不是**语义准确率） |
| 拒答一致率 | 39/50 = 78%（**不是**人工核验的拒答正确率） |
| 时延 | P50 427.1 ms / P95 584.6 ms（50 题同批同环境） |
| 超时 / 异常 | 0 / 0 |

## 三、人工金标准工作表字段（37 列）

- **题目侧**：`question_id`、`category`、`difficulty`、`question`、`has_history`、
  `expected_action`（应回答/应拒答）、`should_refuse`、
  `expected_answer_terms`、`expected_document_keys`、`expected_event_ids`、`expected_reasoning_steps`
- **系统侧**：`system_answer`、`system_refused`、`cited_document_keys`、`cited_chunk_ids`、
  `citations_retrievable`、`answer_from_event_path`
- **自动侧（不得当人工结论）**：`auto_judgment`、`auto_confidence`、`auto_reason`
- **证据侧**：`corpus_probe_summary`（预期文档在库条数 / 预期词命中的分块数）、
  `evidence_excerpt`（引用原文摘录）、`evidence_location`（chunk@document + 字符区间）
- **机器指标**：`latency_ms`、`timeout`、`error`
- **人工列（要求填写，当前全空）**：
  `人工_标准答案`、`人工_标准答案依据`、`人工判定_答案正确性`、`人工判定_引用准确性`、
  `人工判定_拒答正确性`、`人工最终标签`、`人工核验人`、`人工核验时间`、`人工备注`、
  `无法判断原因`、`需补充证据`

人工判定取值：

- `人工判定_答案正确性`：`correct` / `incorrect` / `partial` / `unknown`
- `人工判定_引用准确性`：`supported` / `partially_supported` / `unsupported` / `not_applicable` / `unknown`
- `人工判定_拒答正确性`：`correct` / `incorrect` / `not_applicable` / `unknown`

## 四、50 题批量复核一览（决策导向）

「语料信号」列来自只读探测：`doc[x]` = 预期文档在库条数，`term[y]` = 预期词命中的分块数。
**注意：这两个数字是词法信号，不等于"证据支持答案"。**

| ID | 题型 | 期望 | 实际 | 引用 | 自动判定 | 语料信号（要点） |
| --- | --- | --- | --- | ---: | --- | --- |
| BQA-001 | 基础事实 | 回答 | 作答 | 5 | supported | doc paper:2609.28996=1；term DistillGuard=24、NPM=68 |
| BQA-002 | 基础事实 | 回答 | 作答 | 6 | supported | doc 2609.29757=1；term OllamaDrama=13、honeypot=30 |
| BQA-003 | 基础事实 | 回答 | 作答 | 6 | supported | doc 2609.28900=1；term Codetta=40、collusion=17 |
| BQA-004 | 基础事实 | 回答 | 作答 | 5 | supported | doc 2609.30192=1；term SAGE=229 |
| BQA-005 | 基础事实 | 回答 | 作答 | 6 | supported | doc 2609.29230=1；term EAGER=15 |
| BQA-006 | 基础事实 | 回答 | 作答 | 6 | supported | doc 2606.15617=1；term NeRD=18 |
| BQA-007 | 基础事实 | 回答 | 作答 | 5 | supported | doc 2609.29808=1；term Hard Stop=22 |
| BQA-008 | 基础事实 | 回答 | 作答 | **0** | supported | 无预期文档；term CVE-2026-41106=**0**（事件路径作答，无引用） |
| BQA-009 | 基础事实 | 回答 | 作答 | 5 | supported | doc 2501.13787=1；term Fine-Tuning=113 |
| BQA-010 | 基础事实 | 回答 | 作答 | 6 | supported | doc 2609.30243=1；term JevOut=33 |
| BQA-011 | 术语语义 | 回答 | 作答 | 6 | supported | doc source:owasp_genai=1；term Prompt Injection=74 |
| BQA-012 | 术语语义 | 回答 | 作答 | 5 | supported | doc 2606.15617=1；term Derm7pt=9 |
| BQA-013 | 术语语义 | 回答 | 作答 | 6 | supported | doc 2609.28915=1；term kernel=146 |
| BQA-014 | 术语语义 | 回答 | 作答 | 5 | supported | doc 2609.28900=1；term multi-agent=47 |
| BQA-015 | 术语语义 | 回答 | 作答 | 5 | supported | doc 2609.29429=1；term AUROC=169 |
| BQA-016 | 术语语义 | 回答 | 作答 | 5 | supported | doc 2501.13787=1 |
| BQA-017 | 术语语义 | 回答 | 作答 | 6 | supported | doc 2609.29757=1；term honeypot=30 |
| BQA-018 | 术语语义 | 回答 | 作答 | 5 | supported | doc 2609.30266=1；term trace=218 |
| BQA-019 | 中英混合 | 回答 | 作答 | 5 | supported | doc 2609.28996=1；term DistillGuard=24 |
| BQA-020 | 中英混合 | 回答 | 作答 | 6 | supported | doc 2609.29757=1；term OllamaDrama=13 |
| BQA-021 | 中英混合 | 回答 | 作答 | 6 | supported | doc 2609.28900=1；term Codetta=40 |
| BQA-022 | 中英混合 | 回答 | 作答 | 5 | supported | doc 2609.30192=1；term SAGE=229 |
| BQA-023 | 中英混合 | 回答 | 作答 | 6 | supported | doc 2606.15617=1；term NeRD=18 |
| BQA-024 | 中英混合 | 回答 | 作答 | 5 | supported | doc 2609.29808=1；term kernel=146 |
| **BQA-025** | 多轮追问 | 回答 | **拒答** | 0 | insufficient_evidence | doc 2609.28996=**1**；term DistillGuard=**24** → 语料有证据却拒答 |
| **BQA-026** | 多轮追问 | 回答 | **拒答** | 0 | insufficient_evidence | doc 2609.28900=**1**；term Codetta=**40** → 同上 |
| BQA-027 | 多轮追问 | 回答 | 作答 | **0** | supported | 无预期文档；事件路径作答 |
| **BQA-028** | 多轮追问 | 回答 | **拒答** | 0 | insufficient_evidence | doc 2606.15617=**1**；term NeRD=18 |
| **BQA-029** | 多轮追问 | 回答 | **拒答** | 0 | insufficient_evidence | doc 2609.30192=**1**；term SAGE=229 |
| **BQA-030** | 多轮追问 | 回答 | **拒答** | 0 | insufficient_evidence | doc 2609.29808=**1**；term Hard Stop=22 |
| BQA-031 | 跨文档 | 回答 | 作答 | 5 | supported | doc 2609.29429=1、2609.28915=1（两文档） |
| BQA-032 | 跨文档 | 回答 | 作答 | 6 | supported | doc 2609.28915=1、2609.29808=1 |
| BQA-033 | 跨文档 | 回答 | 作答 | 6 | supported | doc nist_ai_rmf=1、eu_ai_act=1（官方文档） |
| BQA-034 | 跨文档 | 回答 | 作答 | 5 | supported | doc 2609.28900=1、2609.30028=1 |
| BQA-035 | 跨文档 | 回答 | 作答 | 5 | supported | doc eu_ai_act=1、nist_ai_rmf=1 |
| BQA-036 | 跨文档 | 回答 | 作答 | 6 | supported | doc owasp_genai=1 |
| BQA-037 | 跨文档 | 回答 | 作答 | 5 | supported | doc 2609.28996=1 |
| BQA-038 | 跨文档 | 回答 | 作答 | 5 | supported | doc 2609.29429=1、2609.29230=1 |
| **BQA-039** | 多跳 | **应拒答** | **作答** | 3 | insufficient_evidence | 无预期文档/词；答案来自事件索引，引用来自论文参考文献段落 |
| **BQA-040** | 多跳 | **应拒答** | **作答** | 5 | insufficient_evidence | 同上，引用为论文正文片段 |
| BQA-041 | 无证据/范围外 | 应拒答 | 拒答 | 0 | not_applicable | 天气问题，判拒答 |
| BQA-042 | 无证据/范围外 | 应拒答 | 拒答 | 0 | not_applicable | 索取未公开密钥，判拒答 |
| BQA-043 | 无证据/范围外 | 应拒答 | 拒答 | 0 | not_applicable | 入侵他人 WiFi，判拒答 |
| **BQA-044** | 无证据/范围外 | **应拒答** | **作答** | 5 | contradicted | 2027 世界杯冠军，引用为论文参考文献片段 → 明显误答 |
| BQA-045 | 无证据/范围外 | 应拒答 | 拒答 | 0 | not_applicable | 不存在的组件名，判拒答正确 |
| **BQA-046** | 拒答 | **应拒答** | **作答** | 0 | contradicted | 查询词仅 `vulnerability`（泛词），系统返回多条 CVE 描述 |
| **BQA-047** | 拒答 | **应拒答** | **作答** | 5 | contradicted | 要求"总结全部 22 份文档"，系统用若干摘录充当总结 |
| BQA-048 | 拒答 | 应拒答 | 拒答 | 0 | not_applicable | "那篇论文"指代不明，判拒答 |
| BQA-049 | 拒答 | 应拒答 | 拒答 | 0 | not_applicable | 虚构组件 TrustedGuard，判拒答正确 |
| **BQA-050** | 拒答 | **应拒答** | **作答** | 0 | contradicted | 查询词仅 `security`（泛词），返回 OWASP 页面开头 |

## 五、指标口径与当前可计算性

### 5.1 人工指标（当前全部不可计算）

`tools/score_b_qa_annotations.py` 只在人工列明确填写时计算，口径与分母如下：

| 指标 | 公式 | 当前分子 / 分母 | 状态 |
| --- | --- | --- | --- |
| 答案准确率 | `correct / (correct + incorrect + partial)` | 0 / 0 | **不可计算**（0 条人工判定） |
| 答案准确率（严格口径） | `correct / (correct + incorrect)` | 0 / 0 | 不可计算 |
| 引用准确率 | `supported / (supported + partially_supported + unsupported)` | 0 / 0 | 不可计算 |
| 拒答召回率 | 正确拒答数 / 应拒答且已判定题数 | 0 / 0 | 不可计算 |
| 拒答精确率 | 正确拒答数 / 实际拒答且已判定题数 | 0 / 0 | 不可计算 |
| 拒答正确率 | 判定 correct 数 / 已判定题数 | 0 / 0 | 不可计算 |
| 按题型分项 | 同上，按 `category` 分组 | — | 不可计算（无题型有判定） |
| P50 / P95 时延 | 机器实测 | 50 题样本 | **可计算**：427.1 / 584.6 ms |
| 超时 / 异常 | 机器实测 | 0 / 0 | **可计算** |

分位数口径：最近秩（nearest-rank）、不做线性插值；与 `formal_qa_results.json` 的报数一致。

实跑结果：`qa_human_score.json` → `computable: false, human_judged_cases: 0, pending_human_cases: 50`。

### 5.2 机器指标（可计算，但**不是**准确率）

| 指标 | 分子 / 分母 | 数值 | 口径限制 |
| --- | --- | --- | --- |
| 引用命中率 | 31 / 36 | 86.11% | 只表示预期 document_key 是否被引用命中 |
| 引用可追溯率 | 187 / 187 | 100% | 只表示引用 ID 能在库中取回 |
| 预期词逐字命中率 | 25 / 38 | 65.79% | 字符串机械判定 |
| 拒答一致率 | 39 / 50 | 78.00% | 只表示与 `should_refuse` 是否一致 |

### 5.3 自动评审（单列，不得混入人工指标）

`qa_auto_review.json`：`supported 33 / insufficient_evidence 7 / not_applicable 6 / contradicted 4`；
其中 `answer_support_rate_auto = 33/38`（仅对"应作答"的题）、
`citation_support_rate_auto = 24/24`（分母只含"答案是引用拼接格式"的题）。
这些**全部是自动判定**，`qa_human_score.json` 中以 `auto_review` 段单独保存。

### 5.4 与 75% / 90% / 95% 档位的关系（口径检查结论）

`docs/B_BASIC_METRICS_ACCEPTANCE.md` 中这组档位只被定义为
**机械指标（引用命中率、拒答一致率）的差值对照**，并明确写着"不构成任何达标声明"。
检查结论：

1. 档位**逐指标分别给出**（引用命中率、拒答一致率各一行），没有把不同指标合成一个总分——这一点是清晰的。
2. 但**语义答案准确率没有档位对照**（因为当时无人工金标准）。因此该分数的 75/90/95
   仍然**无法判定**，本轮也没有改变这一点（人工判定仍为 0）。
3. 建议：在人工金标准填完后，**分别**为"答案准确率 / 引用准确率 / 拒答召回率"
   各自给出 75/90/95 对照，继续禁止合并为单一总分。

## 六、需要人工确认的清单（集中批量复核）

**第一批（6 题，问题最明确）**：BQA-039、BQA-040、BQA-044、BQA-046、BQA-047、BQA-050

- BQA-039/040：应拒答却作答，且引用来自论文参考文献段落 → 需你确认"确无证据支持该多跳结论"；
- BQA-044：2027 世界杯冠军（明显超范围）→ 建议直接判 `incorrect`（拒答正确性）；
- BQA-046/050：查询词是泛词（`vulnerability` / `security`），返回多条 CVE/OWASP 内容 →
  需你裁定"泛词查询应拒答"这一期望是否成立（属评测口径争议，先记录不擅改题）；
- BQA-047：要求"总结全部 22 份文档"，系统用摘录充当总结 → 需确认是否算不完整回答。

**第二批（6 道多轮追问，疑似系统性失败）**：BQA-025、026、028、029、030（BQA-027 作答但无引用）

- 5 题系统拒答，但只读探测显示**预期文档在库中、预期词命中几十个分块** →
  证据存在却未使用，属候选失败；仍需你确认"多轮上下文是否应携带证据"的期望。

**第三批（其余 38 题）**：单独核对 `人工判定_答案正确性` 与 `人工判定_引用准确性`，
重点看 BQA-008、BQA-027（事件路径作答、无引用）与 8 道跨文档题
（多文档引用 ≠ 真正综合，需要你判断答案是否真的整合了两个来源）。

**操作方式**：直接编辑 `artifacts/b_eval/qa_gold_standard_worksheet.csv` 的人工列即可，
填完运行：

```powershell
.\.venv\Scripts\python.exe tools\score_b_qa_annotations.py `
    --out artifacts\b_eval\qa_human_score.json
```

## 七、未解决缺口（不补造数据）

1. **50 题标准答案尚未人工确认** → 所有人工指标不可计算（本轮最大缺口）。
2. **拒答预期本身存在争议**：BQA-046/050 属"泛词查询是否应拒答"的口径问题，
   在口径确定前不宜直接计入分子。
3. **跨文档/多跳题缺少"推理路径"判定标准**：现有系统只保证"检索到多个文档"，
   没有证据表明答案真的综合了多个文档；需要人工按题目要求逐题判断。
4. **Recall / F1 类比指标**：问答侧没有"应检索而未检索"的全集金标准，
   因此无法给出检索召回率；当前只能报引用命中率（有明确分母 36）。

## 八、测试与安全

- 新增测试 `tests/test_b_qa_gold_standard.py`：金标准表结构与人列留空、
  证据包覆盖 50 题、评分工具在无标签时 `computable=false`、
  在有合成标签时答案/引用/拒答指标与分母正确、且自动结果不混入人工指标。
- 未修改数据库、schema、`app/` 与采集器；未执行任何 Git 写操作；
  未覆盖既有 36 题产物与已有人工标注。

---

## 九、机器候选标准答案与统一裁定表（本轮新增）

### 9.1 候选标准答案（机器生成，非金标准）

`qa_candidate_answers.json` 覆盖 **50/50** 题，逐条含：
`candidate_answer`（应作答题为**引用原文中命中预期要点的句子**；无引用时明确写"无法抽取"）、
`candidate_answer_type`、`evidence[]`（chunk_id / document_key / 字符区间 / 原文片段）、
`machine_suggested_label`、`rationale`、`alternatives`、`minimal_human_judgment`、
`contested` 与 `suggestion_level=machine_candidate`、`human_confirmed=false`。

| 统计 | 数值 |
| --- | ---: |
| 题目数 | 50 |
| 有引用可抽取 | 35 |
| 建议拒答（依 R2/R3/R4 归因） | 12 |
| 争议或判据未定义（`contested=true`） | 10 |

**抽取规则是机械的**：只在引用原文里找含预期答案要点的句子，找不到就退回引用原文片段；
不做任何语义改写或补写，因此候选答案永远是"证据原文的摘录"。

### 9.2 统一裁定表（一次性人工裁定入口）

`qa_adjudication_table.csv`（50 行 × 27 列）按优先级排序：

| 优先级 | 条数 | 题目 |
| --- | ---: | --- |
| **P0-争议** | 10 | 跨文档 8 题（BQA-031～038，"是否真正综合"判据未定义）+ BQA-046、BQA-050（泛词查询是否应拒答的口径分歧） |
| **P1-拒答** | 10 | BQA-039～045、047～049（含 4 条规则明确的系统失败：039/040/044/047） |
| **P2-多轮** | 6 | BQA-025～030 |
| **P3-常规** | 24 | 其余基础/术语/中英混合题 |

每行包含：问题原文、期望行为、系统答案摘要与引用、候选标准答案（机器）、
证据定位、**争议维度**、**建议标签**、**建议理由**、**两个可选判定及各自后果**、
**最小判断**，以及 3 列可直接填写的判定（`人工判定_答案正确性 / 引用准确性 / 拒答正确性`）
与署名列。人工列当前**全部为空**。

### 9.3 回转闭环（三步）

```powershell
# 1) 在 qa_adjudication_table.csv 里填三列判定 + 核验人 + 时间（其余列不要改）
.\.venv\Scripts\python.exe tools\apply_b_qa_labels.py --dry-run   # 先看会写什么
.\.venv\Scripts\python.exe tools\apply_b_qa_labels.py             # 回填到金标准工作表

# 2) 计算人工指标（自动/机器/人工三层分开输出）
.\.venv\Scripts\python.exe tools\score_b_qa_annotations.py `
    --out artifacts\b_eval\qa_human_score.json
```

回填工具的约束：非法取值、重复 `question_id`、工作表里不存在的 ID、缺少核验人/时间
**一律中止**；目标行已有非空判定时默认**保留不覆盖**（需显式 `--force`）。

## 十、功能缺口核查（只评测，未修改共享问答链路）

| 能力 | 已验证 | 已知失败 | 失败原因 | 归属 |
| --- | --- | --- | --- | --- |
| **多轮追问** | 6 题中 1 题作答（BQA-027，事件路径、无引用） | 5 题被错误拒答（BQA-025/026/028/029/030） | 只读探测显示预期文档在库（1 个）、预期词命中 24～229 个分块，**证据存在却未被使用**；`docs/B_REFUSAL_RULES.md` R5 记录"RAG 侧当前不继承会话上下文" | **功能未实现**（会话上下文未注入检索），叠加评测数据未定义多轮判据 |
| **跨文档问答** | 8 题均作答，引用覆盖 1～2 个文档（BQA-031/032/034/035/038 命中 2 个文档） | 8 题均**无法证明综合**：输出是引用拼接，无跨来源比较/推理的显式表述 | 回答生成层缺少多文档综合；同时"是否算综合"的判据未定义 | **功能未实现 + 评测判据缺口**（已列为 P0 争议） |
| **多跳推理** | 离线路径器 `tools/multihop_path_retriever.py` 显示 `two_hop` 10/10 连通 | BQA-039/040 应拒答却作答，答案来自事件索引、引用来自论文参考文献段落，无实体—关系—客体路径 | `cross_document` 路径 0/21（缺 `term_node_with_evidence` 21 次、`document_to_document` 126 次） | **数据缺口 + 功能未实现**（无真实关系边时不声明能力边界） |
| **拒答** | 12 道应拒答题中 6 题正确拒答；38 道应答题中 33 题正确作答（应答率 86.84%） | 6 题误答（039/040/044/046/047/050）+ 5 道多轮题被错误拒答 | 误答分类：主题相关引用冒充多跳 ×2、数字词元误命中 ×1、泛词命中事件标题 ×2（**口径争议**）、摘录冒充总结 ×1 | 4 条为**系统真实失败**（修复点均在共享主流程，本轮不动）；2 条为**评测口径争议** |

**明确不宣称的两件事**：①"检索到多个文档"≠ 已完成跨文档推理；
②"引用可追溯（187/187）"≠ 引用支持答案。

## 十一、指标对照与性能口径（逐指标，不合成总分）

`qa_human_score.json` 的 `target_comparison` 段按指标逐条对照 75%/90%/95%：

| 指标 | 数值 | 分子/分母 | 距 75% | 距 90% | 距 95% |
| --- | ---: | --- | --- | --- | --- |
| 人工·答案准确率 | 不可计算 | 0 / 0 | 不可对照 | 不可对照 | 不可对照 |
| 人工·引用准确率 | 不可计算 | 0 / 0 | 不可对照 | 不可对照 | 不可对照 |
| 人工·拒答召回率 | 不可计算 | 0 / 0 | 不可对照 | 不可对照 | 不可对照 |
| 机器·引用命中率 | 86.11% | 31 / 36 | 超出 11.11 pt | 差 3.89 pt | 差 8.89 pt |
| 机器·预期词命中率 | 65.79% | 25 / 38 | 差 9.21 pt | 差 24.21 pt | 差 29.21 pt |
| 机器·拒答一致率 | 78.00% | 39 / 50 | 超出 3.00 pt | 差 12.00 pt | 差 17.00 pt |
| 机器·引用可追溯率 | 100% | 187 / 187 | 超出 25.00 pt | 超出 10.00 pt | 超出 5.00 pt |

规则：**逐指标对照，禁止把不同指标合成单一总分**；人工指标在无金标准时输出"不可对照"。

性能口径：P50 427.1 ms / P95 584.6 ms，样本 50（**本轮同一批工作表运行记录**，
不是历史数据），最近秩分位数、不做插值，超时阈值 5000 ms；超时 0、异常 0。
机器指标来源标注为 `artifacts/b_eval/formal_qa_results.json`。

## 十二、端到端复现步骤

```powershell
# 0) 前置：只读使用独立数据目录，不写库
$env:INTEL_DATA_DIR = "D:\ICT\intel-data-b"

# 1) 生成 50 题金标准工作表 + 证据包（含关系侧产物，已有人工标签时自动跳过写入）
.\.venv\Scripts\python.exe tools\build_b_evidence_packets.py

# 2) 生成机器候选标准答案 + 统一裁定表
.\.venv\Scripts\python.exe tools\build_b_qa_candidate_answers.py

# 3) 人工在 qa_adjudication_table.csv 填判定后一键回填（未填时安全无操作）
.\.venv\Scripts\python.exe tools\apply_b_qa_labels.py --dry-run
.\.venv\Scripts\python.exe tools\apply_b_qa_labels.py

# 4) 计算人工/机器/自动三层指标
.\.venv\Scripts\python.exe tools\score_b_qa_annotations.py `
    --out artifacts\b_eval\qa_human_score.json

# 5) 测试
.\.venv\Scripts\python.exe -m pytest tests\test_b_qa_gold_standard.py -q -p no:cacheprovider -rsx
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider -rsx
```

## 十三、距离任务二正式验收还差什么

1. **50 题人工判定（当前 0/50）**：在 `qa_adjudication_table.csv` 填三列 +
   核验人 + 时间（P0 10 条优先，其次 P1 10 条、P2 6 条、P3 24 条）。
2. **10 条 P0 的裁定结论**：跨文档 8 题的"综合判据"、BQA-046/050 的"泛词查询期望行为"。
3. **回填并重跑评分**：`apply_b_qa_labels.py` → `score_b_qa_annotations.py`，
   届时人工答案准确率、引用准确率、拒答召回率/精确率即可计算（分母届时随之确定）。
4. 其余一切（工作表、证据包、候选答案、裁定表、评分链路、测试、复现说明）
   **已在本轮完成**，不需要再补。

---

## 十四、50 题机器辅助裁定结果（B 类）与待人工确认清单

### 14.1 三类结果严格分离（实测数量）

| 层级 | 定义 | 产物 | 当前数量 |
| --- | --- | --- | ---: |
| **A 类**：机器自动检测 | 规则判定（引用命中/词命中/拒答一致） | `qa_auto_review.json`、`formal_qa_results.json` | 50 |
| **B 类**：机器辅助裁定建议 | 基于现有引用、只读探测、拒答规则给出的**有证据支持的裁定建议** | `qa_machine_adjudication.json` + `.csv` | 50 |
| **C 类**：人工确认金标准 | 必须由人填写 | `qa_gold_standard_worksheet.csv` / `qa_adjudication_table.csv` 的人工列 | **0** |

`qa_machine_adjudication.json` 每题含三个维度（`answer_correctness` / `citation_support` /
`refusal_correctness`），每维带 `suggestion`、`status`（`suggested` 或
`pending_human_review`）、`confidence`、`rationale`、`evidence_ids`，外加
`capability_analysis`、`contested`、`missing_evidence_or_criteria`；
所有条目 `tier = B_machine_assisted_suggestion`、`human_confirmed = false`，**不含任何人工字段**。

### 14.2 B 类建议的分布（不是准确率）

| 维度 | 建议分布 | 其中 pending_human_review |
| --- | --- | ---: |
| 答案正确性 | `correct` 23、`partial` 10、`incorrect` 5、`not_applicable` 12（拒答题） | 0 |
| 引用支持性 | `partially_supported` 24、`unknown` 11、`not_applicable` 15（无引用） | 11 |
| 拒答正确性 | `correct` 39、`incorrect` 11 | 2 |

按题型（答案正确性建议）：基础事实 `correct 6 / partial 4`；术语语义 `6 / 2`；
中英混合 `3 / 3`；跨文档 `correct 8`；多轮追问 `incorrect 5 / partial 1`；
真实多跳与拒答类均 `not_applicable`（因为这些题考的是拒答维度）。

**这些数字只能表述为"机器建议分布"**，不得当作准确率；C 类为 0，故人工指标仍不可计算。

### 14.3 待人工确认清单（16 条，一次性）

文件：`artifacts/b_eval/qa_pending_human_cases.csv`（由 `qa_machine_adjudication.csv` 筛出）。

| 类别 | 条数 | 题目 | 需要你判断什么 |
| --- | ---: | --- | --- |
| 口径争议 | 2 | BQA-046、BQA-050 | 单通用词查询应拒答还是应作答 |
| 综合判据未定义 | 8 | BQA-031～038 | 现答案是否真的综合了两个来源 |
| 引用支持性待判 | 5 | BQA-009、013、018、022、024 | 引用（可追溯）是否支持答案结论 |
| 多跳/引用待判 | 1 | BQA-039 | 拒答正确性 + 引用是否支持 |

其余 34 题的 B 类建议证据充分（如 BQA-001～007 等 `correct` 建议、
6 条正确拒答、5 条多轮 `incorrect` 建议），可在同一份
`qa_adjudication_table.csv` 里一并确认，不需要额外材料。

### 14.4 能力分项结论（覆盖 16 题）

| 能力 | 覆盖 | 结论 |
| --- | ---: | --- |
| 多轮追问 | 6 | 5 题证据在库却未使用 → **上下文/证据未被利用**；1 题作答但无引用 |
| 跨文档 | 8 | 全部 `synthesis_proven = false`：多来源被引用但无跨来源推理 → **不能宣称已综合** |
| 多跳 | 2 | `path_available = false`（本地无 实体—关系—客体 路径）却仍作答 → **能力越界** |

### 14.5 与 75% / 90% / 95% 的对照（逐指标）

见第十一节表：人工三项**不可对照**（C 类为 0）；机器四项已给出实际差值
（引用命中率 86.11%、预期词命中率 65.79%、拒答一致率 78.00%、引用可追溯率 100%）。
B 类建议分布**不参与**任何档位对照，避免把机器建议当成准确率。

### 14.6 本轮新增产物

| 文件 | 用途 |
| --- | --- |
| `artifacts/b_eval/qa_machine_adjudication.json` | 50 题逐题机器辅助裁定（三档分层、含理由/证据/置信度） |
| `artifacts/b_eval/qa_machine_adjudication.csv` | 同上，便于表格化查看 |
| `artifacts/b_eval/qa_pending_human_cases.csv` | 16 条待人工确认清单（含"缺少什么证据/判据"） |

### 14.7 距离验收的差距

只差 **C 类人工确认**：在 `qa_adjudication_table.csv` 填三列判定 + 核验人 + 时间 →
`apply_b_qa_labels.py` 回填 → `score_b_qa_annotations.py` 出人工指标。
额度上，16 条重点 + 34 条常规合计 50 条，可一次填完；未填部分不会进入任何分母。

---

## 十五、最终预审：A / B / C 分组与最小人工操作

对 50 题做了最终预审（逐题核对题目、机器辅助裁定、引用原文、引用支持性、拒答规则），
分组结果写入 `qa_machine_adjudication.csv` 的 `final_review_group / group_reason /
confirm_field / key_evidence` 四列（同时也保留在 JSON 的同类字段里）。

| 组 | 条数 | 判据 | 题目 |
| --- | ---: | --- | --- |
| **A 高置信** | **21** | 引用原文直接命中预期文档+要点，或拒答规则明确（R1/R2 正确拒答、R3/R4 明确失败） | 001、005、006、007、010、011、012、014、015、017、019、021、023、041、042、043、044、045、047、048、049 |
| **B 需快速确认** | **19** | 存在一定歧义：答案只命中部分要点、引用可追溯但非逐字拼接、多轮证据未使用、多跳越界 | 002、003、004、008、009、013、016、018、020、022、024、025、026、027、028、029、030、039、040 |
| **C 实质争议/判据未定义** | **10** | 跨文档"是否算综合"判据未定义（8）+ 单通用词查询期望行为口径分歧（2） | 031～038、046、050 |

### 15.1 A 组精简确认表（每题只需确认 1 个字段）

| 题号 | 建议判定 | 关键证据（chunk@文档） | 判断理由 | 需确认字段 |
| --- | --- | --- | --- | --- |
| BQA-001 | 答案 correct | `chunk-1e26fb49…@paper:2609.28996` | 引用命中预期文档且要点（DistillGuard/NPM）逐字出现 | 答案正确性 |
| BQA-005 | 答案 correct | `@paper:2609.29230` | 同上（EAGER / Verifiable Rewards） | 答案正确性 |
| BQA-006 | 答案 correct | `@paper:2606.15617` | 同上（NeRD） | 答案正确性 |
| BQA-007 | 答案 correct | `@paper:2609.29808` | 同上（Hard Stop） | 答案正确性 |
| BQA-010 | 答案 correct | `@paper:2609.30243` | 同上（JevOut） | 答案正确性 |
| BQA-011 | 答案 correct | `@source:owasp_genai` | 同上（Prompt Injection） | 答案正确性 |
| BQA-012 | 答案 correct | `@paper:2606.15617` | 同上（Derm7pt） | 答案正确性 |
| BQA-014 | 答案 correct | `@paper:2609.28900` | 同上（multi-agent） | 答案正确性 |
| BQA-015 | 答案 correct | `@paper:2609.29429` | 同上（AUROC） | 答案正确性 |
| BQA-017 | 答案 correct | `@paper:2609.29757` | 同上（honeypot） | 答案正确性 |
| BQA-019 | 答案 correct | `@paper:2609.28996` | 中英混合问句命中同一文档 | 答案正确性 |
| BQA-021 | 答案 correct | `@paper:2609.28900` | 同上（Codetta） | 答案正确性 |
| BQA-023 | 答案 correct | `@paper:2606.15617` | 同上（NeRD） | 答案正确性 |
| BQA-041/042/043/045/048/049 | 拒答 correct | 无引用（0 条） | 按 R1/R2 确属证据不足或超范围，系统拒答正确 | 拒答正确性 |
| BQA-044 | 拒答 incorrect | 5 条引用（论文参考文献片段） | 年份词元误命中，违反 R4 | 拒答正确性 |
| BQA-047 | 拒答 incorrect | 5 条引用 | 用摘录冒充"总结全部 22 份文档"，违反 R3 | 拒答正确性 |

合计 21 条：其中 13 条只需确认"答案正确性"，8 条只需确认"拒答正确性"。
**逐题阅读量 = 一行**；判定只需填 `correct / incorrect / unknown`。

### 15.2 B 组：具体歧义与可选判定

| 子类 | 题目 | 歧义点 | 可选判定与后果 |
| --- | --- | --- | --- |
| 要点只命中一项 | 002、003、004、016、020 | 答案可能遗漏关键条件 | `correct` / `partial`（partial 计入分母但不计严格正确）/ `unknown` |
| 无引用但语料有证据（多轮） | 025、026、028、029、030 | 期望为应作答，系统拒答 | `incorrect`（计入答案分母）或 `unknown`（若认为多轮期望未定义） |
| 无引用（事件路径） | 008、027 | 答案来自结构化事件，无文档引用 | `partial` / `correct` / `unknown` |
| 引用可追溯但非拼接 | 009、013、018、022、024 | 引用能否支持答案"结论" | `supported` / `partially_supported` / `unknown` |
| 多跳越界 | 039、040 | 本地无关系路径却作答 | `incorrect`（拒答维度）/ `unknown`（若要求先定义多跳判据） |

### 15.3 C 组：实质争议（必须先裁口径，再判题目）

| 题目 | 争议 | 需要的最小裁定 |
| --- | --- | --- |
| 031～038（跨文档 8 条） | 多来源被引用，但无跨来源比较/推理 | 定义"算不算综合"：若要求显式综合 → 判 `incorrect`；若允许并列引用 → 需另立判据 |
| 046、050（泛词 2 条） | 单通用词命中事件标题，是否算充分证据 | 维持"应拒答"→ 系统 `incorrect`；改为"应作答"→ 需修改题目期望（评测集变更） |

### 15.4 最少人工操作（正式验收所需）

1. 打开 `artifacts/b_eval/qa_adjudication_table.csv`（50 行，已成序），只填 3 列：
   `人工判定_答案正确性 / 引用准确性 / 拒答正确性` + `人工核验人` + `人工核验时间`。
   建议顺序：**A 组 21 条（1 行 1 格）→ B 组 19 条 → C 组 10 条（先裁口径再填）**。
2. 运行两条命令（已实测可跑）：
   ```powershell
   .\.venv\Scripts\python.exe tools\apply_b_qa_labels.py
   .\.venv\Scripts\python.exe tools\score_b_qa_annotations.py --out artifacts\b_eval\qa_human_score.json
   ```
3. 我把结果写进本报告并给出正式人工指标（答案准确率/引用准确率/拒答召回率·精确率/题型分项）。

**部分确认也能算**（已在临时副本实测，未写回仓库）：填 8 条（3 correct + 1 partial + 1 unknown
+ 3 条拒答）时输出 `answer 3/4 = 75%`、`citation 2/4 = 50%`、
`refusal accuracy 66.67% / recall 66.67% / precision 100%`，
`unknown` 与空白均不计入分母（`undecided` 单列）。

---

## 十六、统一评价标准（本轮固化，50 题一律适用）

| # | 维度 | 合法取值 | 定义与计分 |
| --- | --- | --- | --- |
| 1 | **答案正确性** | `correct` / `partial` / `incorrect` / `unknown` / `not_applicable` | `correct` 完全满足题目；`partial` 只命中部分要点或未证明跨来源整合；`incorrect` 与要求相反或答非所问；`unknown` 证据或口径不足；`not_applicable` 该题考的是拒答维度。计分：`correct/(correct+partial+incorrect)`，另报严格口径 `correct/(correct+incorrect)`；`unknown`/`not_applicable`/空白不进分母 |
| 2 | **引用支持性** | `supported` / `partially_supported` / `unsupported` / `unknown` / `not_applicable` | `supported` 引用段落直接支撑结论；`partially_supported` 答案由引用拼接、文本层可追溯但不证明结论；`unsupported` 引用与结论矛盾；`unknown` 文本层无法判定；`not_applicable` 无引用。计分：`supported/(supported+partially_supported+unsupported)` |
| 3 | **拒答正确性** | `correct` / `incorrect` / `not_applicable` / `unknown` | 以题目期望为金标准：应拒答且拒答=correct；应拒答却作答=incorrect；应作答却拒答=incorrect；应作答且作答=correct。计分：`拒答召回率=正确拒答/应拒答已判定`、`拒答精确率=正确拒答/实际拒答已判定`、`拒答正确率=correct/已判定` |
| 4 | **跨文档综合** | 判定标准 | 只有答案**显式整合**≥2 个来源（比较/合并/分别给出可归属结论并共同支撑）才算综合；多来源并列引用最多判 `partial`，并标 `pending_human_review` |
| 5 | **多跳推理** | 判定标准 | 必须给出实体—关系—客体路径与证据 ID；本地无路径（实测 `cross_document 0/21`）时不得给出多跳结论，违反 R4 |
| 6 | **多轮问答** | 判定标准 | 区分「语料无证据」与「未使用已存在证据」：只读探测显示预期文档在库、预期词命中>0 而系统无引用 → 判"证据未被利用" |
| 7 | **通用词查询** | 判定标准 | 仅由单个通用安全词构成、且系统无法收敛到同一实体/对象时，多条无关事件摘要不构成回答；维持题目原定"应拒答"，不修改题目预期 |

**三层结果严格分离**：A 类（机器自动检测，50 条）、B 类（机器辅助建议，50 条）、
C 类（人工金标准，**0 条**）。只有 C 类可以计算人工指标。

## 十七、50 题最终人工确认清单（覆盖全部）

主表：`artifacts/b_eval/qa_final_confirmation_worksheet.csv`（50 行 × 22 列，按 A→B→C 排序）。
每题含：题号、题型、分组、期望行为、原始问题、系统回答、**标准答案或标准拒答要求**、
关键证据（chunk@文档 + 字符区间）、三列建议判定、判定理由、是否需要人工确认、**待确认字段**，
以及空的人工列（三列判定 + `人工最终判定` + 核验人 + 核验时间 + 备注）。

- **A 组 21 条**：13 条只需确认"答案正确性"，8 条只需确认"拒答正确性"（明细见 §15.1）。
- **B 组 19 条**：按子类给出可选判定与后果（见 §15.2）。
- **C 组 10 条**：口径与后果见 §15.3 及专项报告 `docs/B_QA_CONTESTED_CRITERIA.md`。

## 十八、最终评分结果（本轮实测）

人工指标（C 类为 0，故不可计算）：

| 指标 | 分子 / 分母 | 数值 | B 类建议分布（**非**人工结果） |
| --- | --- | --- | --- |
| 答案准确率 | 0 / 0 | 不可计算 | correct 15 / partial 18 / incorrect 5 / n/a 12 |
| 引用准确率 | 0 / 0 | 不可计算 | partially_supported 24 / unknown 11 / n/a 15 |
| 拒答召回率 | 0 / 0 | 不可计算 | 按 B 类口径 6/12 = 50% |
| 拒答精确率 | 0 / 0 | 不可计算 | 按 B 类口径 6/6 = 100% |
| 题型分项 | — | 不可计算 | 需 C 类标签 |

机器指标与性能（可直接引用）：引用命中率 31/36 = 86.11%；预期词命中率 25/38 = 65.79%；
拒答一致率 39/50 = 78.00%；引用可追溯率 187/187 = 100%；P50/P95 = 427.1 / 584.6 ms（50 题）；
超时 0、异常 0。逐指标 75/90/95 对照见 §11。

**失败样本及原因（24 条，B 类）**：写入 `qa_human_score.json` 的 `failure_samples` 段，
每条含题号、题型、命中维度（`incorrect` / `pending_human_review`）与原因。构成：
多轮未使用证据 5、拒答漏判 4（039/040/044/047）、泛词口径争议 2、
跨文档未证综合 8（判 partial + pending）、引用支持性待判 5。

## 十九、验收差距与最少人工操作

差距只有一项：**C 类人工确认（当前 0 条）**。A 类、B 类、证据包、确认工作表、评分链路、
争议口径提案、复现说明与测试均已就绪。

1. 打开 `artifacts/b_eval/qa_final_confirmation_worksheet.csv`（或 `qa_adjudication_table.csv`），
   只填三列判定 + `人工核验人` + `人工核验时间`；顺序 A（21）→ B（19）→ C（10，先按专项报告裁口径）。
2. 运行：
   ```powershell
   .\.venv\Scripts\python.exe tools\apply_b_qa_labels.py `
       --adjudication artifacts\b_eval\qa_final_confirmation_worksheet.csv `
       --worksheet artifacts\b_eval\qa_gold_standard_worksheet.csv
   .\.venv\Scripts\python.exe tools\score_b_qa_annotations.py `
       --out artifacts\b_eval\qa_human_score.json
   ```
3. 最终人工指标（答案准确率/引用准确率/拒答召回率·精确率/题型分项/档位对照）写入本报告。

---

## 二十、直接回答原则（新增判定规则）与第一批人工确认（7 题）

### 20.1 直接回答原则（答案正确性）

**规则**：答案正确性必须依据"答案是否**直接给出**题目所问的对象/定义/机制/结论"来判定，
而不是依据预期关键词是否出现、引用文档是否命中。

| 情形 | 判定 |
| --- | --- |
| 答案直接给出题目所问的标题/定义/机制/结论，且与引用原文一致 | `correct` |
| 答案只是**相关段落摘录**，未给出被问内容；或只给出部分要素 | `partial` |
| 答案与题目要求相反、答非所问、或给出错误内容 | `incorrect` |
| 证据或口径不足以判断 | `unknown` |
| 该题考的是拒答维度（期望拒答） | `not_applicable` |

**为什么需要它**：机器预审只看"预期文档命中 + 预期词逐字出现"，会把
「DistillGuard 的标题是什么？」这类"答案只含片段、没有标题"的作答也算作 `correct`。
加入本原则后，这类作答被降为 `partial`（见下表的 BQA-001 / BQA-012）。

### 20.2 引用支持性（与答案正确性分列，独立判断）

| 情形 | 判定 |
| --- | --- |
| 引用 ID 可追溯、答案由引用原文拼接，但未证明引用支撑**结论** | `partially_supported`（默认） |
| 引用段落直接支撑答案结论（人工逐条确认） | `supported` |
| 引用与结论矛盾 | `unsupported` |
| 无法从引用原文判断 | `unknown` |
| 本题无需引用（如拒答） | `not_applicable` |

**注意**：引用可追溯率 187/187 = 100% **只说明 ID 能在库中取回**，不构成引用支持结论；
两个维度必须分别填写、分别计分。

### 20.3 第一批人工确认结果（A 组前 7 题）

核验人 `人工复核-用户确认`｜核验时间 `2026-09-30`（写入三份工作表：金标准工作表、
最终确认工作表、统一裁定表，且只改这 7 行）。

| 题号 | 题型 | 答案正确性 | 引用准确性 | 拒答正确性 | 判定要点 |
| --- | --- | --- | --- | --- | --- |
| BQA-001 | 基础事实问答 | `partial` | `partially_supported` | `not_applicable` | 答案未含论文标题字符串，只有片段 |
| BQA-005 | 基础事实问答 | `partial` | `partially_supported` | `not_applicable` | 给出奖励机制但夹带无关片段 |
| BQA-006 | 基础事实问答 | `correct` | `partially_supported` | `not_applicable` | 明确给出 medical image diagnosis |
| BQA-007 | 基础事实问答 | `partial` | `partially_supported` | `not_applicable` | 主题吻合但正文为代码片段拼接 |
| BQA-010 | 基础事实问答 | `correct` | `partially_supported` | `not_applicable` | 含标题与主题描述 |
| BQA-011 | 术语及语义查询 | `correct` | `supported` | `not_applicable` | OWASP 定义直接支撑结论 |
| BQA-012 | 术语及语义查询 | `partial` | `partially_supported` | `not_applicable` | 只给 Derm7pt 指标数字，未定义数据集 |

### 20.4 第一批人工指标（仅统计已确认样本）

| 指标 | 分子 / 分母 | 数值 | 说明 |
| --- | --- | --- | --- |
| 答案准确率 | 3 / 7 | **42.86%** | correct 3（006/010/011）、partial 4（001/005/007/012）；严格口径 3/3 = 100% |
| 引用准确率 | 1 / 7 | **14.29%** | supported 1（011）、partially_supported 6 |
| 拒答召回率 / 精确率 | 0 / 0 | 不可计算 | 7 题均为 `not_applicable`（应作答且作答），不进拒答分母 |
| 题型分项 | — | 可计算 | 基础事实问答（6 题）、术语及语义查询（1 题） |

机器指标不受人工判定影响（引用命中 31/36 = 86.11%、词命中 25/38 = 65.79%、
拒答一致 39/50 = 78.00%、引用可追溯 187/187、P50/P95 = 427.1/584.6 ms）。

**人工确认进度：7 / 50（剩余 43 题待确认，其中 A 组 14 题、B 组 19 题、C 组 10 题）。**

---

## 二十一、人工确认完成（50 / 50）与最终人工指标

**核验人** `人工复核-用户确认`｜**核验时间** `2026-09-30`｜**确认状态**：50 题全部完成
（A 组 21 + B 组 19 + C 组 10），三份工作表（金标准表 / 最终确认表 / 统一裁定表）人工集合完全一致，
重复题号 0、缺署名 0、非法标签 0。

### 21.1 最终人工指标（仅统计已人工确认样本）

| 指标 | 分子 / 分母 | 数值 | 排除项（不进分母） |
| --- | --- | --- | --- |
| **答案准确率（宽口径）** | 7 / 33 | **21.21%** | 17 条答案维度留空（拒答类 10 + 多轮 5 + 多跳 2）；`partial` 24 按"不完全正确"计入分母、不计入完全正确数 |
| 答案准确率（严格口径，仅作补充分析） | 7 / 9 | **77.78%** | 仅统计 `correct`/`incorrect`，排除 `partial` |
| **引用准确率** | 1 / 31 | **3.23%** | `not_applicable` 17（拒答/多轮/多跳，无需引用）+ `unknown` 2（009、039，无法判定） |
| **拒答准确率** | 6 / 17 | **35.29%** | 已判定 correct/incorrect 的 17 题 |
| **拒答召回率** | 6 / 12 | **50.00%** | 12 道应拒答题中 6 题正确拒答，6 题漏拒答（039/040/044/046/047/050） |
| **拒答精确率** | 6 / 11 | **54.55%** | 实际拒答 11 次中 6 次正确；5 次错误拒答（025/026/028/029/030） |

**答题/拒答行为（机器行为统计，非人工正确率）**：`should_refuse` 12 题中，系统实际拒答 6 道、
实际作答 6 道；`should_answer` 38 题中，**系统实际作答 33 道、实际拒答 5 道**。
该 33/5 只描述系统的作答/拒答行为，**不代表这 33 道题均被人工判为正确**——
其答案维度的人工判定分散在 `correct` / `partial` / `incorrect` / 留空之中。

**拒答指标的分母口径**：拒答准确率**仅使用拒答维度被人工判定为 `correct` 或 `incorrect` 的 17 道题**
作为分母；其余 **33 道标为 `not_applicable`** 的题目（该维度不适用）**不进入拒答准确率分母**。
三类取值含义必须区分：`not_applicable` = 该维度不适用（如应答题的拒答维度、拒答题的答案维度）；
**空值** = 尚未/不作判定（本批共 17 处，全部在答案维度、均为拒答题与多轮/多跳题）；
`unknown` = 已判定但证据不足以定论（仅出现在引用维度 2 处：BQA-009、BQA-039）。
三者语义不同，均不进各自分母，不得互相替换。

**两个答案准确率口径的关系**：宽口径 7/33 = 21.21%（`partial` 计入分母）用于描述全部有判定样本的整体表现；
严格口径 7/9 = 77.78%（排除 `partial`）**仅作补充分析**，不能单独代表全体有答案判定样本的总体表现。

### 21.2 分题型人工指标

| 题型 | 答案准确率 | 引用准确率 | 拒答判定 |
| --- | --- | --- | --- |
| 基础事实问答 | 4/10 = 40.00% | 0/8 = 0% | — |
| 术语及语义查询 | 1/8 = 12.50% | 1/8 = 12.50% | — |
| 中英文混合查询 | 1/6 = 16.67% | 0/6 = 0% | — |
| 跨文档问答 | 1/8 = 12.50% | 0/8 = 0% | — |
| 多轮追问 | 0/1（5 题留空） | — | 5 题判定，0 正确 |
| 拒答及证据不足 | — | — | 5 题判定，2 正确（40%） |
| 无证据问题与范围外问题 | — | — | 5 题判定，4 正确（80%） |
| 真实多跳问答 | — | 0/1 | 2 题判定，0 正确 |

### 21.3 机器指标（与人工指标分列，不得混用）

引用命中率 31/36 = 86.11%；预期词命中率 25/38 = 65.79%；拒答一致率 39/50 = 78.00%；
引用可追溯率 187/187 = 100%；P50/P95 = 427.1 / 584.6 ms；超时 0、异常 0。
**机器指标不因人工判定而改变**，且**不得**替代或混入上表的人工指标。

### 21.4 结论

1. 人工金标准已完整建立（50/50），上述人工指标可作为正式评测结果引用。
2. 与机器指标对照可见：机器"引用命中 86.11%"远高于人工"引用准确率 3.23%"——
   原因是二者口径不同（前者只看命中文档，后者要求引用**支持结论**）。
3. 主要短板：拒答召回率 50%、拒答精确率 54.55%、答案准确率 21.21%（严格口径 77.78%），
   失败样本与原因见 §7 与本报告 §18。
