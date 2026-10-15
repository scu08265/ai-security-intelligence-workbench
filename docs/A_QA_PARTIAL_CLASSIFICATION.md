# A1：把"部分正确"拆成可修的清单

对应任务书 2026-10-15 的 A1。产物：

- `tools/classify_qa_partial_cases.py`（分类工具，只读，可重跑）
- `reports/qa-partial-classification.json`（逐题分桶与依据）
- `app/rag.py::_answer_sentence_candidates`（第 2 类的修复）

## 1. 分类口径

输入是两份已有文件，工具只做连接、不重新评分：

| 来源 | 用途 |
| --- | --- |
| `artifacts/b_eval/qa_final_confirmation_worksheet_20261002.csv` | 人工判定（`人工判定_答案正确性`、`人工判定_引用准确性`） |
| `artifacts/b_eval/formal_qa_results_20261002.json` | 机器事实（期望术语、答案全文、引用原文） |

范围：答案被标 `partial` 的 26 题 并上 引用被标 `partially_supported` 的 27 题 = **28 道去重题**。

分桶只用两个确定性事实：期望术语是否逐字出现在答案里、是否出现在引用原文里。

| 桶 | 判据 | 该修哪一层 |
| --- | --- | --- |
| 1 `answer_missing_terms` | 答案里确实缺期望术语 | 答案拼装（`intelligence.answer_question` 的选句与拼装） |
| 2 `citation_does_not_support` | 答案有术语，但引用原文里没有 | 选句逻辑（`rag.assemble_context` 的 `_answer_sentence_candidates`） |
| 3 `rubric_review` | 两边都有，人工仍判部分 | **判定标准问题，交 B 复核**；本轮不动标准 |

## 2. 分类结果（针对 2026-10-02 那批人工判定）

```
scoped: 28 题（答案 partial 26 / 引用 partially_supported 27）
1 answer_missing_terms      : 3
2 citation_does_not_support : 3
3 rubric_review             : 22
```

| 桶 | 题号 | 说明 |
| --- | --- | --- |
| 2 | BQA-004 | 期望术语 `Topological` 不在引用原文里 |
| 2 | BQA-020 | 期望术语 `OllamaDrama` 不在引用原文里 |
| 2 | BQA-038 | 期望术语 `Reinforcement` 不在引用原文里 |
| 1 | BQA-013 / BQA-024 | 答案缺 `kernel` |
| 1 | BQA-022 | 答案缺 `SAGE` |
| 3 | 其余 22 题 | 机器事实两边都在，人工仍判部分，属标准复核 |

第 3 类占 22/28（79%）这件事本身就是结论：这批"部分正确"多数不是代码缺陷，而是判定标准比"术语出现"更严。按任务书要求，标准归 B 复核，本轮不为了好看放宽。

## 3. 第 2 类的修复：选句打分里的同义词重复计分

### 3.1 缺陷

`rag._answer_sentence_candidates` 用 `len(overlap)*2 + len(specific)*2` 给候选句打分，而 `terms()` 会把中文短语扩展成多个英文同义词。于是问句里的"论文"注入 `paper/study/arxiv` 后，论文里到处都有的样板句靠两个同义词各得一分，就能压过真正命中主题词的句子。

2026-10-02 那批答案里能看到这个后果：BQA-004「SAGE 这篇论文的方法名称是什么？」选中的"直接证据"是

```
"Question: Does the paper describe potential risks incurred by study participants, whether …"（IRB 知情同意清单）
```

它同时含有 `paper` 和 `study`，两个注入同义词各算一份，于是压过了含 `SAGE` 的句子。这与已合并的检索修复（`9ff7383`，同义词组按一个概念计分）是同一类缺陷，只是发生在选句层。

### 3.2 改法

`_answer_sentence_candidates` 里把注入的同义词组按一个概念计分：先从计数里剔除注入词，再对"命中过注入词"整体加一次固定权重。主题词仍然各算一份，所以真正含主题词的句子稳定胜出。

### 3.3 实测（本机 `D:\ICT\intel-data-b` 副本上重跑 50 题）

工具：`tools/run_b_qa_eval.py`（只读副本，不写语料）。

| 指标 | 改前 | 改后 |
| --- | ---: | ---: |
| 引用命中率 | 0.9722（35/36） | 0.9722（35/36） |
| 预期词命中率 | 0.9211（35/38） | 0.9211（35/38） |
| 拒答一致率 | 0.84（42/50） | 0.84（42/50） |
| 引用可追溯 | 222/222 | 222/222 |
| 响应耗时 p50 / p95 | 730.6 / 1091.4 ms | 723.0 / 1220.0 ms |

机器指标没有下降（三项主指标完全相同）。改后有 5 题答案变化（BQA-003 / 011 / 016 / 034 / 049），抽查都是往好的方向：

- BQA-011：从 `"(prompt injection) solved the injected task: followed-but-wrong."` 换成三条直接讲 prompt injection 与越狱关系的句子；
- BQA-016：从一句无关的交叉引用 `"PEFT for Visual Content Generation Models subsection subsume the scope of the multi-modal model as"` 换成 `"PEFT FOR MULTI-MODAL FOUNDATION MODELS"`。

## 4. 一个必须如实说明的复核结果

把 28 道题在当前代码上重跑再分一次桶：

```
1 answer_missing_terms      : 3（BQA-013 / 022 / 024，未变）
2 citation_does_not_support : 2（BQA-004 / 020）
3 rubric_review             : 23
```

而那 2 道追下去，期望术语只出现在文档标题里（`SAGE: … via Topological Guidance`、`OllamaDrama: Designing and Deploying a Honeypot …`），被检索到的分块正文里根本没有这个词：

```
BQA-004  term 'Topological'  在引用的分块正文里出现 0 次
BQA-020  term 'OllamaDrama'  在引用的分块正文里出现 0 次
```

也就是说，"引用的标题里出现了答案、但引用正文里没有"算不算支撑，是一个口径/标准问题，不是选句逻辑能修的缺陷。按任务书"A 只修代码、标准归 B 复核"的分工，这 2 道并入第 3 类交 B。

第 2 类的最终结论：选句层的代码缺陷（同义词重复计分）已修，指标不降；剩下的"引用不支撑"是标准问题，交 B。

## 5. 交给 B 的两件事

1. 第 3 类 23 道的判定标准复核：机器事实显示期望术语同时出现在答案与引用原文里，人工仍判部分。需要 B 明确"部分支持"的判据到底是什么——是要求引用正文逐字包含答案要点，还是允许标题与元数据承载。
2. 第 1 类 3 道的答案完整性（BQA-013 / 022 / 024）：答案确实缺 `kernel` / `SAGE`。这属于答案拼装层，需要先确认是"该说的没说"还是"语料里就只有这些"，本轮未改动，留作下一轮。

## 6. 复跑

```powershell
.\.venv\Scripts\python.exe tools\classify_qa_partial_cases.py
.\.venv\Scripts\python.exe tools\run_b_qa_eval.py --out work\qa-eval\after.json
```

分类工具只读两份产物；评测工具先把 `D:\ICT\intel-data-b\intel.sqlite` 复制到临时目录再跑，不写语料源目录。
