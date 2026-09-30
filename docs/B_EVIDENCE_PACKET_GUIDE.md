# B 任务：人工核验工作包使用指南

本指南配套 `tools/build_b_evidence_packets.py` 生成的证据工作包，目的是把
「逐条翻数据库找原文」压缩成「打开文件、看证据、填一个格子」。

**工作包里没有任何人工结论。** 所有标签列、核验人、核验时间都留空；
自动核验（`auto_*`）只是**机器给出的待验结论**，不能直接抄成人工标签。

---

## 一、文件清单与生成命令

| 文件 | 内容 | 行数 / 条目 |
| --- | --- | --- |
| `artifacts/b_eval/evidence_packet_relations.md` | 关系证据核验工作包（含原文片段与定位） | 34 条（12 fixed_version + 22 CVSS） |
| `artifacts/b_eval/evidence_packet_qa.md` | 问答证据核验工作包（含答案、引用原文、语料探测） | 36 道 |
| `artifacts/b_eval/evidence_relation_label_sheet.csv` | 关系标签回收表（可直接回灌） | 34 行 |
| `artifacts/b_eval/evidence_qa_label_sheet.csv` | 问答标签回收表 | 36 行 |
| `artifacts/b_eval/evidence_packet_coverage.json` | 覆盖率、冲突与缺失证据清单 | 汇总 |

重新生成（只读数据库、不联网）：

```powershell
.\.venv\Scripts\python.exe tools\build_b_evidence_packets.py
```

该脚本只读本地快照与真实数据库（`sqlite3` 以 `mode=ro` 打开），
**不写入数据库、不发起网络请求**，也不覆盖任何既有评测产物。

---

## 二、关系核验（34 条）

### 2.1 每条包含什么

`evidence_packet_relations.md` 中每条记录包含：

- 主体 / 关系 / 客体、候选值（`candidate_value`）；
- 自动核验结论与规则明细（`R-FV-*`、`R-CVSS-*` 等）；
- **证据状态**：`direct` = 本地有可直接读取的原文；
- **证据定位**：`snapshots/<source>/<文件>.json → <字段路径>`，可直接按路径打开核对；
- **证据片段**：从该定位处抽出的原文（截断时标注「已截断」）；
- **冲突提示**与**需要人工确认的问题**；
- 空白的最终标签、核验人、核验时间、备注。

### 2.2 三类冲突提示的含义

CVSS 的 22 条全部带冲突提示，且都不是编造，含义如下：

| 类型 | 条数 | 含义 |
| --- | --- | --- |
| MSRC `TemporalScore` 与候选 `BaseScore` 口径不一致 | 9 | 冒烟快照同时给了基础分与时序分（如 `BaseScore=9.3`、`TemporalScore=8.1`），要确认候选取的是哪一种口径 |
| 候选 `score=null` | 12 | 上游（OSV）只提供了向量、没有基础分，候选因此没有分数；需确认是「上游未提供」还是「采集遗漏」 |
| NVD 记录只有 Secondary 来源 | 1 | `CVE-2025-9959` 的 CVSS 由 `reefs@jfrog.com` 提供，不是 NVD 自评 |

候选向量与证据向量**逐字比对不一致**的情况当前为 0 条；若出现，会在同处明确列出候选值与证据值。

### 2.3 判定标签的定义（与既有评分工具一致）

只能填以下四个值（大小写不敏感，回灌时统一转小写）：

| 标签 | 含义 |
| --- | --- |
| `positive` | 依据证据确认该关系**成立**——金标准正例 |
| `negative` | 依据证据确认该关系**不成立**——金标准负例 |
| `unknown` | 现有证据不足以定论（含来源缺失、来源之间冲突且无法裁决） |
| `not_applicable` | 经证据确认该关系**不适用**（例如该产品根本不由该来源维护） |

具体到两个维度：

- **fixed_version**：同时核对（a）产品/包名是否为同一对象、（b）受影响区间下界与修复版本是否自洽
  （修复版本不应落在受影响区间内）、（c）来源公告是否给出同一版本号。三者不一致时按 `unknown` 处理并写备注。
- **CVSS**：核对分数、向量（含 `E/RL/RC` 等时序分量）、版本前缀（`CVSS:3.1` / `CVSS:4.0`）
  是否来自同一条记录；同一 CVE 存在多个分数或向量时，**不能取平均**，必须在备注里写明取哪一条及理由。

### 2.4 填完标签后怎么算指标

```powershell
# 1) 回灌：CSV → JSON（不覆盖原始候选）
.\.venv\Scripts\python.exe tools\apply_b_relation_labels.py `
    --worksheet artifacts\b_eval\evidence_relation_label_sheet.csv `
    --out artifacts\b_eval\relation_candidates_labeled.json

# 2) 统计 TP / FP / FN 与 Precision
.\.venv\Scripts\python.exe tools\score_b_relation_annotations.py `
    --input artifacts\b_eval\relation_candidates_labeled.json
```

口径提醒（评分脚本已内置）：

- 只有 `human_verified` 且标签明确的记录进入分母；空白、`unknown`、`not_applicable` 单列不计入。
- **Precision 可算**；**Recall / F1 在没有「应抽取但未抽取」的金标准清单时不可计算**，
  脚本会如实输出 `null` 并说明原因。候选集本身就是系统输出，其中天然不含漏检项。

> 本工作包的对应产物：回灌输出 `artifacts/b_eval/relation_candidates_labeled_fi12.json`，
> 评分输出 `artifacts/b_eval/relation_score_fi12.json`（见第七节）。为避免覆盖既有产物，
> 这两份结果使用独立文件名，不改动 `relation_candidates_labeled.json` 等上一轮文件。

---

## 三、问答核验（36 道）

### 3.1 选题优先级

36 道由 `_qa_priority` 选取，覆盖顺序为：

1. 指定的 6 道拒答重点题：`BQA-039/040/044/046/047/050`（工作包前 6 条）；
2. 其余**应拒答**题（当前 50 道里共 12 道，已全部覆盖）；
3. **多轮追问**题（6 道，已全部覆盖）；
4. 带明确推理步骤的跨文档 / 多跳题（16 道，已全部覆盖）；
5. 其余按题号补足。

### 3.2 每条包含什么

- 问题、类别、预期（应回答 / 应拒答）、实际（作答 / 拒答）；
- 预期答案要点、预期文档；
- **系统实际回答**（过长时截断并标注）；
- **引用证据逐条**：`chunk_id`、`document_key`、字符区间与引用原文片段；
- **自动信号（非人工结论）**：文档命中、词命中、引用是否可取出、异常与超时；
- **语料只读探测**：预期文档在库中的条数、预期词在分块中出现的次数（词法信号）；
- 自动评审结论与规则明细、需要人工确认的问题、空白判定栏。

### 3.3 判定要点

1. **两层分开核验**：先看引用 ID 是否真的能在数据库取回（可追溯性），
   再看引用内容是否**支持**答案中的具体结论（支持性）。两者不能混为一谈。
2. **有证据但没引用** 与 **真的没证据** 是两件事。`语料只读探测` 显示预期文档在库、
   预期词命中了若干分块，却没有任何引用时，属于**系统失败**；两者都为 0 时才可能是「语料缺失」。
3. 需要全量总结、跨文档综合、多轮追问的题，必须按题目要求核验，
   不能因为关键词命中就判为正确；用若干摘录拼接冒充完整总结应记为不通过。
4. 拒答题只有在「确实缺少必要证据」或「问题超出系统能力边界」时才算正确；
   反之，有证据却拒答同样是失败。

---

## 四、当前证据状况（由脚本实测，非估计）

| 项目 | 结果 |
| --- | --- |
| fixed_version | 12 / 12 具备可读取的 OSV 结构化证据（`affected[].ranges[].events[].fixed`） |
| CVSS | 22 / 22 具备可读取证据（MSRC 9 条 / OSV 12 条 / NVD 1 条） |
| 关系条目完全缺失证据 | 0 |
| 问答条目 | 36 道；21 道系统返回了引用（共 111 条引用片段可读），15 道无任何引用 |
| 关系标签回收表 | 34 行，列名与 `apply_b_relation_labels.py` 对齐，已用回灌工具实测可读（0 标签 / 34 空白） |

---

## 五、时间有限时的核验建议

**只有 10 分钟**：先看 `evidence_packet_qa.md` 前 6 条（拒答相关），
重点确认 `BQA-039 / 040 / 044` 这类「应拒答却作答」的题目是否真的缺少证据；
再抽查 `BREL-CV-0001`（TemporalScore 口径冲突）与任一 `BREL-FI-*`（fixed_version 全绿）。

**有 30 分钟**：在上一档基础上，把 22 条 CVSS 的冲突提示过一遍
（9 条时序分口径 + 12 条 `score=null` + 1 条 Secondary 来源），
并把 6 道多轮题的语料探测结论与系统回答对照。

---

## 六、明确限制

- 本工作包**不产生**任何准确率、召回率或人工核验结论；没有人工标签时 Precision/Recall/F1 一律标注为不可计算。
- 自动评审结果（`auto_*`）与语料只读探测都是**机器信号**，不得改写为人工判定。
- 工作包不解决「语料里到底有没有完整证据」的语义判断，这仍然需要人工阅读引用原文与来源文档。
- 带 `TemporalScore` 的 MSRC 记录同时包含基础分与时序分，本工作包不做取舍，交给人工按评测口径裁定。

---

## 七、第一批人工核验记录（fixed_version 12 条）

**核验方式**：逐条展示候选关系、自动核验结论、OSV 结构化范围与 `details` 正文，由人工给出判定；
自动结论未被采信为人工结论。**核验人** `人工复核-用户确认`，**核验时间** `2026-09-28`。

**结果**：`positive` 10 条、`unknown` 2 条、`negative` / `not_applicable` 0 条。

| relation_id | 关系 | 判定 |
| --- | --- | --- |
| BREL-FI-0001 | PYSEC-2026-4000 → vllm@0.30.0 | positive |
| BREL-FI-0002 | PYSEC-2026-3998 → vllm@0.29.0 | positive |
| BREL-FI-0003 | PYSEC-2026-3999 → vllm@0.30.0 | positive |
| BREL-FI-0004 | PYSEC-2026-3997 → vllm@0.28.0 | positive |
| BREL-FI-0005 | PYSEC-2026-3996 → vllm@0.30.0 | positive |
| BREL-FI-0006 | GHSA-8pw2-6jv3-mj5j → vllm@0.28.0 | **unknown** |
| BREL-FI-0007 | GHSA-hcwq-8wjf-3gcr → vllm@0.24.0 | positive |
| BREL-FI-0008 | PYSEC-2026-3985 → vllm@0.28.0 | positive |
| BREL-FI-0009 | GHSA-wvm9-9g5j-623f → open-webui@0.11.1 | positive |
| BREL-FI-0010 | GHSA-3g9q-v48f-hh9w → open-webui@0.11.1 | positive |
| BREL-FI-0011 | GHSA-v39v-59xw-j98g → open-webui@0.11.1 | positive |
| BREL-FI-0012 | GHSA-mcmc-2m55-j8jj → vllm@0.13.0 | **unknown** |

两条 `unknown` 的原因（详见工作表 `人工备注` 列）：

- **BREL-FI-0006**：结构化 `affected` 区间（`introduced=0`、`fixed=0.28.0`）与 `details` 正文冲突；
  正文明确表示受影响范围应为「包含引入提交 `af16446bf` 的 `main` 构建」，而非已确认的发布版本范围，
  且正文从未提及 `0.28.0`。
- **BREL-FI-0012**：`details` 全文不含任何版本号、也无 release tag 引用，
  `fixed=0.13.0` 仅有结构化 `range` 支持，需核验 PR `#30649` 的合并记录与正式发布版本。

**备注口径**：12 条统一使用「依据 OSV 快照 `affected[].ranges[].events` 与 `details`；
未独立核验上游修复提交。」作为前缀，再按条目追加差异说明。

**评分口径与实测结果**（`tools/score_b_relation_annotations.py`）：

```
fixed_version   total=12  pending=0  undetermined=2  TP=10  FP=0  FN=0  P=1.0  R=null  F1=null
cvss            total=22  pending=22 ...
paper_link      total=37  pending=37 ...
version_range   total=50  pending=50 ...
```

**必须注意的口径限制**：

1. 这里的 `P=1.0` 只覆盖已核验的 **12 条 fixed_version**，不代表其余 3 个维度（共 109 条候选）的准确率。
2. `recall` / `F1` 仍为 `null`：候选集本身就是系统输出，没有「应抽取而漏抽」的金标准全集，FN 无来源。
3. 自动核验给这 12 条全部判 `supported`，人工将其中 **2 条下调为 `unknown`**——
   这是「自动支持率 ≠ 准确率」的第一个实证，后续报告不得把 `supported` 直接当作正确。

---

## 八、第二批人工核验记录（CVSS 22 条）

**核验人** `人工复核-用户确认`，**核验时间** `2026-09-28`。自动结论 22 条全为 `supported`，
人工判定与其在 12 条上出现分歧（见下）。

### 8.1 本批确认的三条口径

| 口径 | 决定 |
| --- | --- |
| A. 分数与向量的关系 | 两者都属于评测对象，但**允许字段缺失**；「向量正确性」与「分数正确性」应分开评估，缺失分数**不得计为正确预测**，也不得当作 0 |
| B. MSRC 基础分 | 统一以 `BaseScore` 作为基础 CVSS 分数；`TemporalScore` 只作备注，两者不得混用；将来需要时序评分应另设字段与口径 |
| C. 来源等级 | 接受有明确来源标识的 Secondary 分数，但必须注明来源等级，不得表述为官方自评 |

### 8.2 标签结果

| 候选范围 | 条数 | 标签 | 备注要求 |
| --- | --- | --- | --- |
| BREL-CV-0001～0009（MSRC） | 9 | positive | BaseScore 与向量均逐字匹配；记录同时给出 TemporalScore（8.1/7.7/8.6/5.7/6.8/8.6/5.7/7.4/7.1），仅作备注 |
| BREL-CV-0010～0021（OSV） | 12 | **unknown** | 向量已与上游 `severity.score` 逐字核实；上游未提供数值分数，候选 `score=null`，缺失分数不参与正确性判定 |
| BREL-CV-0022（NVD） | 1 | positive | baseScore 7.6 与向量均匹配；分数由 `reefs@jfrog.com` 提供，属 NVD 记录中的 **Secondary** 来源，不得表述为 NVD 自评 |

合计：`positive` 10 条、`unknown` 12 条。全部 22 条备注均记录了证据定位与上述口径。

### 8.3 为什么 OSV 的 12 条是 `unknown` 而不是 positive（结构性原因）

候选的关系定义是 `relation = has_cvss`，其 `candidate_value` 为
`{version, score, vector}` 的**复合声明**，维度 `verification_method` 写明
「确认 **score 与 vector** 逐字一致，且确实来自该来源」；而
`tools/apply_b_relation_labels.py` 与 `tools/score_b_relation_annotations.py` 使用的标注结构只有
**单一 `label` + 自由文本 `note`**，无法分别记录「向量判定」与「分数判定」两级结果。

因此按事先约定的规则：**结构不支持字段级判定时，整体保留 `unknown` 并在备注中写明
「向量已核实、分数缺失」**，而不是把 12 条整体标成 positive 或把缺失分数算作正确。

若将来需要让这 12 条以「向量 positive / 分数未验证」进入指标，需要先做两件事（**本轮未实施**）：
① 标注表增加字段级列（如 `向量判定` / `分数判定`）；② 评分脚本按字段分别统计，
并明确「分数缺失」单独计数而不是并入 TP。这属于标注与评分口径的扩展，需单独授权。

### 8.4 字段级核验覆盖（与标签分开统计）

| 核验对象 | 已验证 | 上游缺失 / 未验证 |
| --- | --- | --- |
| CVSS **向量**（22 条） | **22 / 22**——全部与上游逐字一致（MSRC `Vector` 9 条、OSV `severity.score` 12 条、NVD `vectorString` 1 条） | 0 |
| CVSS **数值分数**（22 条） | **10 / 22**——MSRC `BaseScore` 9 条 + NVD `baseScore` 1 条 | **12 / 22** 上游未提供数值分数（OSV 仅给向量），候选如实记 `null`，不计为正确、也不计为错误 |

### 8.5 评分口径与实测结果

命令与产物（为避免覆盖第一批结果，使用独立文件名）：

```powershell
.\.venv\Scripts\python.exe tools\apply_b_relation_labels.py `
    --worksheet artifacts\b_eval\evidence_relation_label_sheet.csv `
    --out artifacts\b_eval\relation_candidates_labeled_human.json
.\.venv\Scripts\python.exe tools\score_b_relation_annotations.py `
    --input artifacts\b_eval\relation_candidates_labeled_human.json `
    --out artifacts\b_eval\relation_score_human.json
```

实测输出：

```
已回灌: 34 条人工标签 / 34 行
  空白: 0 | positive: 20 | negative: 0 | unknown: 14 | not_applicable: 0

cvss            total=22  pending=0  undetermined=12  TP=10  FP=0  FN=0  P=1.0  R=null  F1=null
fixed_version   total=12  pending=0  undetermined=2   TP=10  FP=0  FN=0  P=1.0  R=null  F1=null
paper_link      total=37  pending=37 ...
version_range   total=50  pending=50 ...
micro: TP=20 FP=0 FN=0, precision=1.0, recall=null, f1=null, evaluable_samples=20
```

**适用范围（必须照此表述）**：

1. `P=1.0` 只覆盖**已人工核验的 34 条**（fixed_version 12 + CVSS 22）；
   `paper_link`（37 条）与 `version_range`（50 条）共 87 条候选仍为 `pending`，未纳入任何指标。
2. `undetermined=14`（CVSS 12 + fixed_version 2）单列，**不计入 P/R 分母**，
   它们表示「证据不足以定论」或「结构无法字段级判定」，不是错误，也不是正确。
3. `recall` / `F1` 仍为 `null`：候选集本身就是系统输出，缺「应抽取而漏抽」的金标准全集，FN 无来源。
4. `micro.evaluable_samples=20` 即 34 条中真正进入分母的条数。

---

## 九、工作表同步与剩余 87 条证据包

### 9.1 两份工作表已对齐（34 条）

`relation_annotation_worksheet_v2.csv`（121 行，回灌工具的**默认** worksheet）原先这 34 行是空白，
现已按 `relation_id` 精确同步 `evidence_relation_label_sheet.csv` 的 34 条标签、核验人、核验时间与备注。

实测核对：**仅 34 行发生变化，且只改了那 4 列；其余 87 行逐字段与原表完全一致**（同步前已备份到
`%TEMP%\relation_annotation_worksheet_v2.backup_20260930.csv`）。用默认 worksheet 跑一遍既有链路：

```powershell
.\.venv\Scripts\python.exe tools\apply_b_relation_labels.py `
    --worksheet artifacts\b_eval\relation_annotation_worksheet_v2.csv `
    --out artifacts\b_eval\relation_candidates_labeled_v2.json
.\.venv\Scripts\python.exe tools\score_b_relation_annotations.py `
    --input artifacts\b_eval\relation_candidates_labeled_v2.json `
    --out artifacts\b_eval\relation_score_v2.json
```

结果与证据表路线**完全一致**（`relation_score_v2.json` 与 `relation_score_human.json` 逐字节相同，
34 条 `annotation` 也完全相同），因此不存在评分脚本歧义，未改动任何评分语义。

### 9.2 剩余 87 条证据包

| 文件 | 内容 |
| --- | --- |
| `artifacts/b_eval/evidence_packet_remaining.md` | paper_link 37 + version_range 50，逐条含候选、证据原文、定位、冲突、缺口与待确认问题 |
| `artifacts/b_eval/evidence_remaining_label_sheet.csv` | 87 行回收表（标签列全空，列名对齐回灌工具） |
| `artifacts/b_eval/evidence_packet_coverage.json` | 新增 `relations_paper_link` / `relations_version_range` / `remaining` 统计 |

证据覆盖（实测）：

- **paper_link 37 条**：候选 PDF 链接 **37/37 逐字出现在本地 OpenAlex work 记录**（`direct`）。
  其中 **16 条**本地已有对应 RAG 全文文档（`paper:<arxiv_id>`，可交叉核验主题），
  另 **21 条**为非 arXiv 链接、未抓取全文，**主题一致性无法本地核验**（已在工作包标注）。
- **version_range 50 条**：候选三元组 **50/50 与事件保存的 `affected[]` 一致**（`direct`）。
  其中 **13 条**有具体区间（OSV 12 条可由 `introduced/fixed` 结构化推导、MITRE 1 条可由
  `{version, lessThan}` 推导，均已复核一致）；另 **37 条 `range=unknown`**
  （MSRC 11 + CISA KEV 26），来源本身不提供版本区间，已在工作包标注为"与来源一致但不构成区间证据"。
- 冲突条目：**0**。

### 9.3 需要人工决定的争议项

1. **`range=unknown` 的 37 条**：与 CVSS 的口径 A 同类——「来源确实没给区间」算不算正确？
   若按「字段缺失不参与正确性判定」处理，应整体保留 `unknown` 并备注；这需要与 CVSS 采用同一口径。
2. **21 条无本地全文的 paper_link**：链接存在性可直接核验，但"论文与事件主题一致"无法本地核验，
   建议同样按口径 A 处理（或标注为「链接证据充分、主题未验证」）。
3. **主题相关性可疑的 paper_link**：部分 OpenAlex 命中与 AI 安全主题关系很弱
   （如 mRNA 疫苗、企业数字化风险、耐药菌管理、需求响应等标题），
  即使链接证据成立，也需要人工判断是否算作有效的"事件—论文关联"。

---

## 十、第三批人工核验记录（剩余 87 条）与最终关系指标

**核验人** `人工复核-用户确认`；**核验时间** 沿用用户此前指定的 `2026-09-28`。本批确认四条口径：

| 口径 | 决定 |
| --- | --- |
| 1. `range=unknown` 的 37 条 | 统一标 `unknown`，备注「来源未提供区间字段」，计入 `undetermined`，不进 Precision 分子/分母 |
| 2. 无本地全文的 21 条 paper_link | 链接存在性与主题相关性分开评估；现有标签结构无法字段级记录 → 整体 `unknown`，备注「链接存在，但缺少充分证据验证论文主题相关性」 |
| 3. 16 条有本地全文的 paper_link | 依据实际全文判断主题相关性；证据充分标 positive，明确矛盾标 negative，无法确定标 unknown |
| 4. VE-0017 / VE-0031 及对应 fixed_version 疑难样本 | 保留 `unknown`，本轮不额外联网调查 |

### 10.1 标签结果

| 维度 | positive | unknown | negative | 合计 |
| --- | --- | --- | --- | --- |
| fixed_version | 10 | 2 | 0 | 12 |
| cvss | 10 | 12 | 0 | 22 |
| paper_link | **16** | **21** | 0 | 37 |
| version_range | **11** | **39** | 0 | 50 |
| **合计** | **47** | **74** | 0 | **121** |

16 条 paper_link 的核验依据（实测）：本地 RAG 全文文档与 OpenAlex 记录**标题逐字一致**，
且正文首部即该论文摘要 → 链接存在性与主题一致性同时成立，判 positive。
其中 2 条（`BREL-PA-0016` 医学影像诊断、`BREL-PA-0031` BT/FSM 转换框架）与"AI 安全"主题的
贴合度偏弱，但论文身份一致，已在报告中单列说明，后续若做主题相关性评分需另行定义标准。

11 条 version_range 的 positive 依据：OSV `introduced/fixed`（10 条）与 MITRE
`{version:"0", lessThan:"1.21.0"}`（1 条）结构化推导出的区间与候选逐字一致。

### 10.2 最终关系评分（121 条全部已核验）

```powershell
.\.venv\Scripts\python.exe tools\apply_b_relation_labels.py `
    --worksheet artifacts\b_eval\relation_annotation_worksheet_v2.csv `
    --out artifacts\b_eval\relation_candidates_labeled_all.json
.\.venv\Scripts\python.exe tools\score_b_relation_annotations.py `
    --input artifacts\b_eval\relation_candidates_labeled_all.json `
    --out artifacts\b_eval\relation_score_all.json
```

```
已回灌: 121 条人工标签 / 121 行
  空白: 0 | positive: 47 | negative: 0 | unknown: 74 | not_applicable: 0

fixed_version  total=12  pending=0  undetermined=2   TP=10  P=1.0  R=null  F1=null
cvss           total=22  pending=0  undetermined=12  TP=10  P=1.0  R=null  F1=null
paper_link     total=37  pending=0  undetermined=21  TP=16  P=1.0  R=null  F1=null
version_range  total=50  pending=0  undetermined=39  TP=11  P=1.0  R=null  F1=null
micro: TP=47 FP=0 FN=0, precision=1.0, recall=null, f1=null, evaluable_samples=47
```

### 10.3 关于「至少 100 条人工核验关系」的达标判断（重要）

- **已人工核验的行数：121 / 121**——从"工作量与覆盖面"看已达到 100 条以上。
- **真正进入 Precision 分母（可判定样本）：47 条**——其余 **74 条**因
  「上游字段缺失」或「标签结构无法字段级判定」被列为 `undetermined`；`negative` 为 0。
- 因此"100 条人工核验关系"这一要求，**在"可判定样本"口径下并未满足（47 < 100）**；
  只能表述为「121 条候选全部完成人工核验，其中 47 条构成可判定样本」。
- `precision = 1.0` 的适用范围仅限这 47 条，**不得**推广为整体关系抽取准确率；
  `recall` / `F1` 仍为 `null`（缺「应抽取而漏抽」的金标准全集）。
- 若要真正达到 100 条可判定样本，需要：① 扩展标签结构以支持字段级判定（可把
  CVSS 12 条与 paper_link 21 条的"部分字段已验证"转化为可判定样本）；
  ② 补齐上游区间/全文证据（需联网，另行授权）；③ 或扩充候选集。
