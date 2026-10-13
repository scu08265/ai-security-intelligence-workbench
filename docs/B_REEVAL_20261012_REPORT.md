# B 项重评测确认（2026-10-12，A1 排序修改后）

## 1. 为什么重跑

`9ff7383`（A1）改了 `app/rag.py` 的排序计分：一个中文短语的同义词组（如 `论文` →
`paper` / `study` / `arxiv`）原先在打分时逐词各计一分，现改为按**一个概念**取其中最强的成员。
这直接改变 `retrieve_chunks` 的返回集合，而问答评测的引用与命中都建立在该集合之上，
因此需要确认已交付的 `artifacts/b_eval/` 数字有没有漂移。

## 2. 方法与口径

* 语料：`D:\ICT\intel-data-b\intel.sqlite`，8,183,808 B / `4095a5b1…8254285`（交付包核验后的同一份）。
  评测脚本 `tools/run_b_qa_eval.py` 自行把库复制到临时目录再跑，源库只读。
* 固定评测集：`evaluation/b_formal_qa_set.json`，50 题，两次运行使用同一份。
* 对照方式：为了把"代码变化"和"环境变化"分开，跑了两次：

  | 运行 | 代码 | 说明 |
  | --- | --- | --- |
  | 对照运行 | `b020090`（A1 之前），独立 worktree | 应当复现已交付的 10-02 批次数字 |
  | 本批运行 | `08a41fa`（含 A1） | 本批次的真实数字 |

  判定标准：若对照运行能逐项复现已交付数字，说明不存在环境漂移，差异只能归因于 A1。

## 3. 结果

| 口径 | 引用命中 `document_hit` | 预期词命中 `term_hit` | 拒答一致率 | 引用总数 |
| --- | --- | --- | --- | --- |
| 已交付 `formal_qa_results_20261002.json` | 32 / 36 = **0.8889** | 31 / 38 = **0.8158** | 42 / 50 = 0.84 | 217 |
| 对照运行（A1 之前 `b020090`） | 32 / 36 = **0.8889** | 31 / 38 = **0.8158** | 42 / 50 = 0.84 | 217 |
| 本批运行（含 A1 `08a41fa`） | 35 / 36 = **0.9722** | 35 / 38 = **0.9211** | 42 / 50 = 0.84 | 222 |

对照运行与已交付产物的四项指标**逐项完全一致**，因此这里的差异不是机器或语料造成的，
而是 A1 带来的确定性变化。作答/拒答结构两次相同（作答 46 / 拒答 4），拒答口径不受影响。

**发生变化的题目（4 题）**：

| 题号 | 变化 | A1 之前的引用 | A1 之后的引用 |
| --- | --- | --- | --- |
| BQA-002 | `term_hit` False → True | — | — |
| BQA-003 | `document_hit` + `term_hit` False → True | `paper:2501.13787`、`paper:2609.29429`、`paper:2609.30192` | `paper:2501.13787`、**`paper:2609.28900`** |
| BQA-005 | `document_hit` + `term_hit` False → True | `paper:2501.13787`、`paper:2609.29429`、`paper:2609.30192` | `paper:2501.13787`、**`paper:2609.29230`** |
| BQA-034 | `document_hit` + `term_hit` False → True | `paper:2501.13787`、`paper:2609.29429`、`paper:2609.30192` | **`paper:2609.28900`**、**`paper:2609.30028`** |

共同点很清楚：A1 之前这三题都被同义词扩展带来的高分论文占满（`paper:2501.13787` 等），
真正应该命中的论文被挤出；A1 之后期望文档直接进了引用集合。

## 4. 关系与 RAG 维度

* **关系评测无漂移**：用同一份标注与金标准重跑，
  `relation_score_gold_20261010.json` 与冻结对照 `relation_score_gold_frozen20261006_20261010.json`
  重跑后与已交付文件**逐字节相同**（SHA-256 `57547561…d3e52ef3` / `6621401e…c6792d01`）。
  该链路不经过 `app/rag.py`，符合预期。
* **RAG 检索**：`tests/test_rag_retrieval_b_task.py` 30 passed；
  `tests/test_rag_mixed_language_query.py` 30 passed（含此前唯一失败的中频词用例）。

## 5. 产物与边界

* 本批新增 `artifacts/b_eval/formal_qa_results_20261012.json`（50 题逐题记录，含引用明细，
  本次运行的实测耗时）。**没有覆盖** `formal_qa_results.json`（2026-09-30 基线）、
  `formal_qa_results_prev.json`、`formal_qa_results_20261002.json`、`formal_qa_results_before_terms_fix.json`。
* 采用新增批次而不是覆盖，理由是该文件是 `tools/auto_review_qa.py`、
  `tools/build_b_qa_candidate_answers.py`、`tools/build_b_review_workpackets.py`、
  `tools/classify_b_refusals.py`、`tools/score_b_qa_annotations.py`、
  `tools/build_b_qa_performance_report.py`、`tools/summarise_auto_review.py` 等下游工具的输入，
  直接覆盖会让这些承载人工标签的产物与机器结果脱节；这与此前 10-02 批次"另存一批、旧文件不动"的做法一致。
* **本轮未重跑**这些下游产物（自动评审、候选标准答案、复核工作包、拒答分类、性能统计）。
  它们的输入仍是 09-30 基线的 `formal_qa_results.json`。是否要把它们刷新到 10-12 批次，
  涉及人工标签是否重签，需队长决定后再做。

## 6. 复现命令

```powershell
# 本批（含 A1）
.\.venv\Scripts\python.exe tools\run_b_qa_eval.py --out artifacts\b_eval\formal_qa_results_20261012.json

# 对照（A1 之前的代码）
git worktree add <临时目录> b020090
cd <临时目录>
<主仓库>\.venv\Scripts\python.exe tools\run_b_qa_eval.py --out <临时输出>\formal_qa_results_preA1.json

# 关系维度（应与已交付文件逐字节相同）
.\.venv\Scripts\python.exe tools\score_b_relation_annotations.py `
    --input artifacts\b_eval\relation_candidates_labeled_20261010.json `
    --gold evaluation\b_relation_gold_20261010.json `
    --out <临时输出>\relation_score_gold_20261010.json
```
