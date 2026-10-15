# 问答 4 题重签材料与建议判定（2026-10-15）

**依据**：A1 的排序修复（`9ff7383`）改变了 BQA-002 / 003 / 005 / 034 的引用集合或答案文本，
而这 4 题在 10-02 批次里的判定（答案 `incorrect`、引用 `unsupported`）是对着旧输出做的。
不重签等于拿旧判定给新输出背书，所以队长决定这 4 题重签、其余 46 题沿用。

**已核实的前提**：用当前 main 的代码重跑一遍 50 题，与冻结的
`artifacts/b_eval/formal_qa_results_20261012.json` **逐题零差异（0 / 50）**，
包括这 4 题的答案与引用。所以重签是对着"当前代码的输出"做的，不会签完就过期。

**本文件的性质**：下面是**建议判定 + 依据**，不是已经写入的签名。
人工判定是人给的结论，需由本人在工作表上确认后才生效。

## 1. 判定尺度

* **引用维度**：按 `docs/B_CITATION_SUPPORT_RUBRIC.md` 的三个可复算信号
  （备而不用 / 引用落点 / 要点覆盖）先算，再人读一遍定主标签。
* **答案维度**：看**答案正文的证据摘录**是否直接回答了问题。
  **标签里的文献标题不算答案内容**——这条尺度是从既有 46 题反推的：
  BQA-001 的答案正文是一段乱码拼接、标题只出现在 `[标签]` 里，当时判的就是 `partial`。

## 2. 逐题材料与建议

### BQA-002 ｜基础事实问答｜OllamaDrama 论文研究的是什么对象？

| 项 | 内容 |
| --- | --- |
| 期望 | 文档 `paper:2609.29757`；要点 `OllamaDrama`、`honeypot` |
| 旧判定（10-02） | 答案 `incorrect` / 引用 `unsupported`（`人工复核-用户确认`，2026-10-04） |
| 新输出（10-12） | `document_hit` ✅、`term_hit` ✅、拒答 ✗；引用 5 条 |
| 新答案正文摘录 | "passive Internet measurement study of real-world attacks targeting LLM API" |
| 标签 | `[OllamaDrama: Designing and Deploying a Honeypot to Measure Attacks on Exposed LLM Infrastructure · chunk-e7c4f5f3c7751a3ffa30b7ce]` |
| 机械信号 | 答案实际使用 2 条 / 引用 5 条（**备而不用 3**）；**非期望文档引用 1 条**（`paper:2501.13787`）→ `off_topic` |
| **建议** | **答案 `partial`**；**引用 `partially_supported`** |
| 依据 | 摘录确实描述了研究对象（对暴露 LLM 的攻击做被动测量），但没有点出 `honeypot`；`honeypot` 只出现在标签标题里，按第 1 节的尺度不计入答案内容。引用里混入了一篇与问题无关的论文 |

### BQA-003 ｜基础事实问答｜Codetta 论文研究的是什么问题？

| 项 | 内容 |
| --- | --- |
| 期望 | 文档 `paper:2609.28900`；要点 `Codetta`、`collusion` |
| 旧判定（10-02） | 答案 `incorrect` / 引用 `unsupported` |
| 新输出（10-12） | `document_hit` ✅、`term_hit` ✅、拒答 ✗；引用 5 条 |
| 新答案正文摘录 | "arXiv preprint arXiv:2310.18512, 2023."（**参考文献条目**） |
| 标签 | `[Codetta: High-Capacity, Keyless, and Undetectable Multi-Agent Collusion · chunk-d7489ff3b07026aca9a7948d]` |
| 机械信号 | 答案实际使用 2 条 / 引用 5 条（备而不用 3）；**非期望文档引用 2 条** → `off_topic` |
| **建议** | **答案 `partial`**；**引用 `partially_supported`** |
| 依据 | 正文摘录是一条参考文献，没有回答问题；研究问题（多智能体合谋）只在标签标题里出现，同样不计入答案内容 |

### BQA-005 ｜基础事实问答｜EAGER 论文使用了什么奖励机制？

| 项 | 内容 |
| --- | --- |
| 期望 | 文档 `paper:2609.29230`；要点 `EAGER`、`Verifiable Rewards` |
| 旧判定（10-02） | 答案 `incorrect` / 引用 `unsupported` |
| 新输出（10-12） | `document_hit` ✅、`term_hit` ✅、拒答 ✗；引用 4 条 |
| 新答案正文摘录 | "anomaly and does not fully model complex phe- orizes, rl generalizes: A comparative study of"（跨行拼接片段） |
| 机械信号 | 答案实际使用 2 条 / 引用 4 条；非期望文档引用 1 条；**两个期望要点 `EAGER`、`Verifiable Rewards` 在所有引文里都没有出现** → `off_topic+insufficient` |
| **建议** | **答案 `partial`**；**引用 `partially_supported`** |
| 依据 | 摘录是乱码拼接，没有说明奖励机制；且期望要点在引用集合里完全缺失——这一条同时是 A1 第 2 类修复的目标样本 |

### BQA-034 ｜跨文档问答｜multi-agent 主题出现在哪些论文中？

| 项 | 内容 |
| --- | --- |
| 期望 | 文档 `paper:2609.28900` + `paper:2609.30028`；要点 `multi-agent` |
| 旧判定（10-02） | 答案 `incorrect` / 引用 `unsupported` |
| 新输出（10-12） | `document_hit` ✅、`term_hit` ✅、拒答 ✗；引用 6 条 |
| 新答案正文摘录 | "We study how multi-agent systems respond to deception as groups grow and deceptive participants"（来自 `2609.28900`），第二条摘录同样来自这两篇 |
| 机械信号 | 答案实际使用 2 条 / 引用 6 条（备而不采用 4）；**非期望文档引用 0 条**；要点未被引用覆盖为空 → `not_signalled`（信号没触发，需人读） |
| **建议** | **答案 `correct`**；**引用 `supported`** |
| 依据 | 引用的两篇文档**恰好就是期望的两篇**，答案正文直接命中 `multi-agent` 并准确复述了论文主题。4 条备而不用属于"引用选取冗余"，是 A1 第 2 类修复的目标，但不构成"引用不支持答案" |

## 3. 重签后的预期变化

| 指标 | 10-02 现状 | 重签后（按上表建议） |
| --- | --- | --- |
| 答案正确性 | correct 5 / partial 26 / incorrect 7（分母 38）→ 13.16% | correct **6** / partial 26 / incorrect **6** → 15.79% |
| 引用支持 | supported 3 / partially_supported 27 / unsupported 6（分母 36）→ 8.33% | supported **4** / partially_supported 27 / unsupported **5** → 11.11% |

两点必须同时说清：

1. 这两项仍然很低（15.79% / 11.11%），**方向本身没错**：问题不在检索（`document_hit` 0.9722），
   而在答案组织与引用选取这两层。
2. 重签**不是为了让数字好看**——上表只是按判定尺度给出的结果；如果人工读完认为某题仍不达标，
   按更低的档位签。

## 4. 待确认

请逐题确认第 2 节的建议判定。确认后我会：

1. 把 4 题的新判定写入 10-12 的工作表（`qa_final_confirmation_worksheet_20261012.csv`），
   其余 46 题沿用 10-02 的判定与署名；
2. 生成 `qa_human_score_20261012.json` 与 `qa_performance_20261012.json`；
3. 让页面活动批次自动切到 20261012（`_active_batch()` 要求两个文件成对，不需要改代码）。
