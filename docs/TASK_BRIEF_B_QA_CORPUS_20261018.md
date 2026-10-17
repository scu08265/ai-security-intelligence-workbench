# 任务书 2026-10-18：B 项问答评测——先修语料，再重判

## 0. 一句话

人工答案准确率 15.79% 的根因**不是"系统答错"，也不是"标注过期"，是论文全文的分栏抽取
把两栏文字织在了一起**。先把 PDF 抽取修好、重建语料，再重跑 50 题、重判。
**不要先动标签。**

---

## 1. 已查明的事实（先读，不要重复查）

### 1.1 现行活动批次（20261012）

| 项 | 读数 |
| --- | --- |
| 答案 | correct 6 / **partial 29** / incorrect 3 / undecided 12 → 6/38 = **15.79%** |
| 引用 | supported 4 / **partially 30** / unsupported 2 / n/a 10 / unknown 4 → 4/36 = **11.11%** |
| 拒答 | 4/12 = 33.33%（精确率 1.0） |

### 1.2 用当前代码重跑同一批 50 题，结果一模一样

产物：`artifacts/b_eval/formal_qa_results_20261017.json`（已入库）。

| 机器指标 | 20261012 批次 | 20261017 重跑 |
| --- | --- | --- |
| 文档命中 | 97.22%（35/36） | 97.22% |
| 预期词命中 | 92.11%（35/38） | 92.11% |
| 拒答一致 | 84%（42/50） | 84% |
| 引用可追溯 | 100%（222/222） | 100% |

逐题比对：**0 题发生变化**。所以不要再用"代码改过了、标注过期"去解释这个数。

### 1.3 证据其实都在

按 `tools/classify_qa_partial_cases.py` 同一套包含规则逐题算：

- 29 条判 partial 的题里，**26 条的答案文本已包含全部预期要点**；
- 32 条判引用弱的题里，**29 条的引用原文已包含全部预期要点**。

不是"没检索到"。判弱的直接原因是**这些句子本身读不通**。

### 1.4 根因：双栏 PDF 被按行交错拼接

代码位置：`app/rag_corpus.py:195`

```python
text = page.extract_text(extraction_mode="layout") or ""
```

`layout` 模式保留视觉版式，双栏论文于是变成"左栏一行 + 右栏一行"交替。实测摘录：

```
BQA-001  chunk-3e02e30d18b6d9d534a09cad
  "With while online pedestal models possess superior secure in- static graph structure feature extraction,
   high-level security inference capabilities, ..."

BQA-004  chunk-03317ba315f16be669e3c769
  "soning as
   a stress test for exploration and compounding biases. Section 5.4 is the ablation study of the two ..."

BQA-014  items
  "1. strawman under realistic multi-agent deployment of model and context asymmetry.Section 6builds the key"
  "2. teurs, Better Fixers: Scaling & Security in Linear Multi-Agent Workflows..."
```

最后一条的 `teurs` 是 `Troublemakers` 的尾巴——这是分栏交错的典型症状。
**这种文本无论用什么答案模板都读不通**，所以组织层的修改救不了人工分。

---

## 2. 任务（按顺序做，前一步不通过不要做下一步）

### B1（最高优先）修 PDF 抽取，并证明它变干净了

两种做法，推荐 a：

- **a（推荐）** 去掉 layout：`page.extract_text()`。pypdf 默认按内容流顺序提取，双栏通常逐栏读出。
- **b** 两种都抽，用可量化指标挑更干净的一份：统计"半句开头"（行首小写拉丁字母）
  与"断词"（行尾 hyphen 且下一行以小写开头）的比例，取更低者。

**硬要求**：

1. 对**同一页**给 before / after 对照：至少 3 篇论文、每篇贴 3–5 行，必须肉眼可见成句。
2. 加单元测试：用固定 fixture 断言抽取结果里"行首小写 + 行尾 hyphen"的密度低于阈值。
   （若造双栏 PDF 成本高，可对后处理函数做单测，但必须在说明里写清覆盖范围。）
3. **只动抽取，不动 chunk 切分参数**——一次只改一个变量，否则无法归因。

**验收**：3 组 before/after 对照 + 1 个新测试；`pytest tests/test_rag_corpus.py` 通过。

### B2 用修好的抽取重建论文语料（在你的机器上）

当前语料规模（我查过）：`rag_documents = 22`、`rag_chunks = 3639`，其中 `paper:*` 16 篇。
原始 PDF **只在你那台机器上**（这台机器 `D:\ICT` 下没有任何 PDF，只有 sqlite）。

要求：

1. **不要覆盖旧目录**。新语料另存，例如 `D:\ICT\intel-data-b-colfix-20261018`，便于对照回滚。
2. 给出重建后的：文档数 / 分块数 / 每篇字数分布。
3. 随机抽 10 个 chunk 贴原文（人工能读懂为准），并标注它们在旧语料里对应的 chunk 长什么样。

**验收**：新旧目录都在；10 条抽样对照；抽样里不再出现 1.4 节那种交错。

### B3 重跑 50 题（机器侧）

```powershell
python tools/run_b_qa_eval.py --out artifacts/b_eval/formal_qa_results_20261018.json
```

**验收**：

- 异常 0 / 超时 0；
- 文档命中、预期词命中**不得低于** 97.22% / 92.11%（修抽取不该把检索弄差）；
- 给出 P50 / P95 延迟（当前基线 P50 459 ms）。

### B4 重判（人工，只有你能签）

1. 以 B3 的新输出为准，复制一份确认表（**不要改 1012 的旧表**）：
   `artifacts/b_eval/qa_final_confirmation_worksheet_20261012.csv`
   → `artifacts/b_eval/qa_final_confirmation_worksheet_20261018.csv`
2. 按 `docs/B_CITATION_SUPPORT_RUBRIC.md` 与 `docs/B_QA_CONTESTED_CRITERIA.md` 的既定标准逐题判，
   填三列（答案正确性 / 引用准确性 / 拒答正确性）+ 署名。
3. 回填与计分：

```powershell
python tools/apply_b_qa_labels.py --adjudication <你的裁定表> --worksheet artifacts/b_eval/qa_final_confirmation_worksheet_20261018.csv --dry-run
python tools/apply_b_qa_labels.py --adjudication <你的裁定表> --worksheet artifacts/b_eval/qa_final_confirmation_worksheet_20261018.csv
python tools/score_b_qa_annotations.py --worksheet artifacts/b_eval/qa_final_confirmation_worksheet_20261018.csv --results artifacts/b_eval/formal_qa_results_20261018.json --out artifacts/b_eval/qa_human_score_20261018.json
```

4. **还必须产出** `artifacts/b_eval/qa_performance_20261018.json`。
   页面切批次的规则是（`app/b_evaluation.py::_active_batch`）：同一个 batch_id 下同时存在
   `qa_human_score_*` 和 `qa_performance_*`，取**最大批次号**。少一个文件，页面不会切，
   报告就会和代码对不上。

**验收**：两份 20261018 产物都在；页面"B 人工问答评测"卡片的批次 id 变成 20261018；
`pytest tests/test_competition_scorecard.py` 通过。

---

## 3. 明确不做

- **不许**把 partial 改成 correct 去凑 75%。判完如果还是 partial，就保留，并在备注写清缺什么。
- **不许**改分母口径。`partial` 计入分母这条写在 `tools/score_b_qa_annotations.py` 的文档里，是既定标准。
- **不许**改 1012 批次的旧产物（它是历史证据），新结果一律用新批次号。
- **不许**把 PDF 或语料提交进仓库（`.gitignore` 既有约定）。

---

## 4. 交付物清单

| 项 | 路径 |
| --- | --- |
| 抽取修复 | `app/rag_corpus.py` + 对应测试 |
| 抽取对照 | 3 篇论文 before/after 摘录（写进交付说明） |
| 新语料 | `D:\ICT\intel-data-b-colfix-20261018`（或同等新目录）+ 10 条 chunk 抽样 |
| 机器结果 | `artifacts/b_eval/formal_qa_results_20261018.json` |
| 人工结果 | `artifacts/b_eval/qa_human_score_20261018.json`、`qa_performance_20261018.json` |
| 判定表 | 带署名的 20261018 裁定表 |
| 一页说明 | 抽取前后 chunk 质量对比、50 题指标前后对比、剩余 partial 的原因分布 |

---

## 5. 时间与顺序

| 步骤 | 预估 |
| --- | --- |
| B1 抽取修复 + 测试 | 40–60 分钟 |
| B2 重建语料 + 抽样 | 20–30 分钟 |
| B3 重跑 50 题 | 10 分钟 |
| B4 重判 + 出两份产物 | 60–90 分钟 |

如果只有今晚：**先做完 B1–B3**（机器侧），B4 第二天补。
在 B4 完成前，页面继续显示 20261012 批次——报告里引用时必须写清批次号与日期，
不能说成"当前代码的成绩"。

---

## 6. 相关文件索引

- 抽取实现：`app/rag_corpus.py`（`_parse_pdf`，第 175–205 行；layout 在第 195 行）
- 评测集：`evaluation/b_formal_qa_set.json`（50 题）
- 评测执行：`tools/run_b_qa_eval.py`
- 判分口径：`tools/score_b_qa_annotations.py` 顶部文档
- 引用判定标准：`docs/B_CITATION_SUPPORT_RUBRIC.md`
- partial 归因工具：`tools/classify_qa_partial_cases.py`
- 待判产物（当前代码，答案已改成"答案：…"开头）：
  `artifacts/b_eval/formal_qa_results_20261017_after_compose.json`
