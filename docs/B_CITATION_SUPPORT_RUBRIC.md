# 引用支持率判定细则（2026-10-15）

**解决的问题**：10-02 批次里 27 题判 `partially_supported` 是个黑洞——"引用句与答案无关"和
"答案需要多句证据、只引了一句"被混在同一个取值里，既让 A1 的第 2 类修复没有明确目标，
也让重签缺少统一尺度。

**做法**：主标签**一个字都不改**（仍是 5 个取值），细则只做两件事——
① 把可机械复算的信号定义清楚；② 在 `partially_supported` 下面给出**子类**，
并单列一份分类产物。这样既不动评分器，也不动既有 50 题的标签。

## 1. 五个主标签（沿用，不改）

| 取值 | 含义 | 是否进引用支持率分母 |
| --- | --- | --- |
| `supported` | 引用集合支持答案的所有断言 | 进 |
| `partially_supported` | 只部分支持（见第 3 节的子类） | 进 |
| `unsupported` | 引用集合没有一条支持答案 | 进 |
| `not_applicable` | 本题不需要引用（应拒答等） | 不进 |
| `unknown` | 证据不足或无法回读，判不了 | 不进 |

口径不变：`引用支持率 = supported / (supported + partially_supported + unsupported)`。

## 2. 三个可复算信号

判定前先算这三个信号，它们是"可复算"的部分；最后的 `supported` / `partially_supported` 边界
仍由人工读一遍原答案与引文确定（第 7 节说明为什么不能全自动）。

### S1 备而不用（引用条数 − 答案实际使用的条数）

答案正文里每条证据摘录都带文档标签，形如：

```
- “引文…” [DistillGuard: Malicious NPM Package Detection … · chunk-1e26fb499bb6dbae04a358d4]
```

标签尾部的 `chunk-…` 与 `citations_detail[].chunk_id` **精确对应**，因此"哪条引用真的被答案用了"
可以逐条对账，不需要模糊匹配：

```
used_chunk_ids   = 答案正文里所有 […] 标签中的 chunk id
citations_unused = citations_detail 里 chunk_id 不在 used_chunk_ids 的条目数
```

### S2 引用落点（引用是否来自期望文档）

```
expected_documents = QA 题集的 expected_document_keys
covers_expected_document = 引用文档集合 ∩ expected_documents 非空
```

**期望文档为空的题（多跳类）不判落点**，结果记为 `null`。
早期版本把"期望文档为空"当成"全部非期望"，导致 BQA-040 被误判成引非所答，已在本轮修正。

### S3 要点覆盖（答案里出现的期望要点是否被引文覆盖）

```
expected_terms_in_answer       = 期望要点中逐字出现在答案里的
expected_terms_not_in_citations = 上者中，在**所有引文**里都找不到的那些
```

这一条能抓住"答案说了、引用里没有"的漏引，例如 BQA-004 的 `Topological`、BQA-020 的 `OllamaDrama`。

## 3. 子类判定（只对 `partially_supported` 判）

| 子类 | 触发条件 | 含义 |
| --- | --- | --- |
| `off_topic` | 引用了**非期望文档**（不论该引用有没有被答案使用）；或引用一条都不在期望文档里 | 引非所答 |
| `insufficient` | 答案实际使用的摘录 ≤ 1 条而引用 ≥ 3 条（"只引了一句却挂了多条引用"）；或答案里出现的期望要点**未被任何引文覆盖** | 证据不足 / 只引了一句 |
| `off_topic+insufficient` | 两者同时成立 | 既有无关引用，又漏引 |
| `not_signalled` | 三个信号都没触发 | 需要人重新读原答案与引文，不能凭信号下结论 |

**`备而不用`（引用条数 − 答案实际使用的条数）是质量信号，不进子类。** 依据：既有判定里
`supported` 的题也有"答案用了 1 条、引用挂了 5 条"的情况（BQA-007、BQA-011），
只凭这个信号区分不了主标签，所以它只作为"引用选取冗余"记录，供 A1 参考。

**主标签怎么定**：`not_signalled` 之外都落在 `partially_supported`；
若引用集合里**没有任何一条**支持答案（人工确认），才落到 `unsupported`。
所以子类是"为什么只是部分支持"的说明，不是新的主标签。

## 4. 27 题的分类结果（可复算）

复算命令：

```powershell
.\.venv\Scripts\python.exe tools\classify_citation_support.py `
    --results artifacts\b_eval\formal_qa_results_20261012.json `
    --worksheet artifacts\b_eval\qa_final_confirmation_worksheet_20261002.csv `
    --out artifacts\b_eval\qa_citation_support_classification_20261012.json
```

结果（产物 `artifacts/b_eval/qa_citation_support_classification_20261012.json`）：

| 子类 | 题数 | 题号 |
| --- | ---: | --- |
| `insufficient` | **22** | 见产物 `cases[].proposed_subclass` |
| `off_topic` | **2** | BQA-014、BQA-015 |
| `not_signalled` | **3** | BQA-031、BQA-032、BQA-040 |
| `off_topic+insufficient` | 0 | — |
| 合计 | **27** | |

支撑数据：

* **答案实际使用的证据条数**：1 条 × 14 题、**0 条 × 8 题**、3 条 × 3 题、2 条 × 2 题
* **备而不用条数**（质量信号）：5 条 × 11、4 条 × 7、6 条 × 4、3 条 × 3、2 条 × 2
* **引用条数**：5 条 × 13、6 条 × 13、4 条 × 1
* **引用全部落在期望文档**：26 / 27（例外是 BQA-014 混入 `paper:2609.30028`、BQA-015 混入 `paper:2609.28915`）
* **期望要点未被引文覆盖**：2 题（BQA-004、BQA-020）

## 5. 给 A1 第 2 类修复的目标

这 27 题里 **22 题（0 条或 1 条）** 的共同形态是：**引用挂了 5–6 条，答案只用了 0–1 条**。
也就是说检索把证据取回来了，是**选句与答案拼装**没有把真正回答问题的那一句挑出来用。
修复目标是确定性的、可复算的：

* 选句：`app/rag.py` 的 `_answer_sentence_candidates` 目前按 overlap 计分，
  同一短语的同义词各算一份（与已修的检索问题同源）——应按"这句是否包含问句的区分性术语"排序，
  而不是按词面重合数量。
* 拼装：`app/intelligence.py` 的答案组织应把**被判为支撑的句子**用上，
  并**去掉备而不用的引用**——引用条数应当等于答案实际引用的条数。

验收：这 26 题里，除非答案确实只需要一句，否则 `备而不用` 应降到 0；
重跑机器指标不得下降。

## 6. 重签 4 题时怎么用这份细则

BQA-002 / 003 / 005 / 034 的重签按同一套尺度：

1. 先算三个信号（同上命令，换 results 为 10-12 批次）；
2. 再人工读一遍新答案与新引文，按第 3 节定子类、按第 1 节定主标签；
3. 判定结果与子类一并写进工作表备注，便于以后复核。

## 7. 局限（为什么不能全自动）

* `supported` 与 `partially_supported` 的边界是**语义判断**：引用句支持的是"答案的断言"，
  而不是"答案里出现了相同词"。本轮实测过：词面重合度在 `supported`（中位 0.127）与
  `partially_supported`（0.125）之间**没有区分度**，所以词面相似度只能当信号、不能当判据。
* 本细则给出的三个信号都是**结构性的**（chunk id 对账、文档落点、要点字面覆盖），
  它们能定位"哪里不对"，但"这句引用是否支撑这句答案"最终仍要人读一遍。
* 子类产物是**建议归类**，不是新的主标签；评分器与既有 50 题标签不受影响。
