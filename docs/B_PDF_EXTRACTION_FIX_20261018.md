# PDF 抽取修复与论文语料重建（2026-10-18）

**结论**：人工答案准确率低的直接原因是**双栏论文被按视觉版式抽成了左右交错**，
不是答案组织、也不是标注过期。修掉 `extraction_mode="layout"` 后重建语料，
**50 题里 31 题的答案文本发生变化**，且变为可读的成句内容；机器指标没有下降。

## 1. 根因

`app/rag_corpus.py::_parse_pdf` 原来用：

    text = page.extract_text(extraction_mode="layout")

`layout` 保留视觉版式，双栏论文于是变成"左栏一行 + 右栏一行"交替。旧语料里的实例
（`paper:2609.28996`，即 DistillGuard）：

    旧：… D. Fine-Tuning tillGuard framework achieves the combined advantages of
        While online pedestal models possess superior secure in- static graph structure
        feature extraction, high-level security ference capabilities, they also suffer from
        insurmountable knowledge reasoning, and lightweight local deployment. limitations, …

`Dis-tillGuard` 被拆成 `Dis-` 与 `tillGuard`、右栏的 `static graph structure …` 插进了左栏句子中间。
**这种文本无论用什么答案模板都读不通。**

## 2. 修复

只改抽取，**不动分块参数**（`DEFAULT_CHUNK_CHARS` / `DEFAULT_OVERLAP_CHARS` 未变）：

* `_parse_pdf` 改用默认内容流顺序：`page.extract_text()`；
* `PARSER_VERSION` 从 `fulltext-1.2` 升到 **`fulltext-1.3`**。
  这一步是必须的：`version_id` 由 `document_id + raw_hash + PARSER_VERSION` 决定，
  不升版的话重新 ingest 会因 id 相同而 skip，旧文本被静默保留（实测 `version_created=False`）。

## 3. before / after 对照（同一页、只差抽取模式）

### 3.1 `paper:2609.29230`（第 4 页，双栏）

**before（layout）**

    GRPO (Shao et al.,2024) and DAPO (Yu et al.,                  outcome rewards{R i}Gi=1 , and estimates the per-
    2026),   has   demonstrated   strong   effectiveness          token advantage as the group-normalized reward:
    across  a  range  of  reasoning  tasks   (Guo  et  al.,
    2025),   however  the  application  of  RLVR  to              ˆAit = Ri−mean  {R i}Gi=1   ,           (4)
    structured  information  extraction  tasks  such  as          std{R i}Gi=1

**after（默认）**

    GRPO (Shao et al., 2024) and DAPO (Yu et al.,
    2026), has demonstrated strong effectiveness
    across a range of reasoning tasks (Guo et al.,
    2025), however the application of RLVR to
    structured information extraction tasks such as

### 3.2 `paper:2609.28996`（第 8 页，正文与表格混排）

**before（layout）**

    among  all  tools.  A  deeper  analysis  of  its  detection  logic          TABLE IV
    reveals  that  OSSGadget  indiscriminately  flags  all  API  calls     RESULTS OFABLATIONSTUDY
    and  keyword  matches  related  to  sensitive  permissions  and      Method   Acc.  Prec.  Rec.  F1.
    high-risk  operations,  regardless  of  whether  they  appear  in
    executable code or possess genuine malicious execution logic.        Full     95.3  99.4  88.9  93.8

**after（默认）**

    among all tools. A deeper analysis of its detection logic
    reveals that OSSGadget indiscriminately flags all API calls
    and keyword matches related to sensitive permissions and
    high-risk operations, regardless of whether they appear in
    executable code or possess genuine malicious execution logic.

### 3.3 `paper:2609.28900`（第 9 页，双栏 + 公式）

**before（layout）**

    ZK as inDefinition 1. Then, every codeword symbol in      c is masked with a fresh pad rt =RangePRF    km(sid,t)        ,
    a pseudorandom function with range ZK  (line 5); for K=2       this is the XOR of c with a PRF bit stream.
    The hash function  fBucket,t     partitions V  into buckets Bt,0 ,...,B t,K−1       that depend only on the token and the
    position (line 6). The bucket masses πt(a) =p         t(B  t,a  ) are known to the sender alone, and their imbalance is
    measured as:

**after（默认）**

    ZK as in Definition 1. Then, every codeword symbol inc is masked with a fresh pad rt =RangePRF km(sid,t) ,
    a pseudorandom function with range ZK (line 5); for K=2 this is the XOR of c with a PRF bit stream.
    The hash function fBucket,t partitions V into buckets Bt,0, . . . ,Bt,K−1 that depend only on the token and the
    position (line 6). The bucket masses πt(a) =p t(Bt,a) are known to the sender alone, and their imbalance is
    measured as:

## 4. 交错片段的出现次数（可复算）

在"当前版本"的分块上按子串计数：

| 交错特征 | 旧语料 | 新语料 |
| --- | ---: | ---: |
| `secure in- static graph`（跨栏断词） | 2 | **0** |
| `insurmountable knowledge reasoning`（跨界搭配） | 1 | **0** |

## 5. 语料重建

**新目录**：`D:\ICT\intel-data-b-colfix-20261018`（旧目录 `D:\ICT\intel-data-b` 原样未动）。
做法：复制旧目录后，用 `fulltext-1.3` 重新 ingest 16 篇 `paper:*`。

| 项 | 旧语料 | 新语料 |
| --- | ---: | ---: |
| `rag_documents` | 22 | 22 |
| `rag_chunks`（含历史版本） | 3,639 | 5,895 |
| `rag_chunks`（当前版本，可检索） | 3,639 | **3,681** |

逐篇字数（当前版本，字符）：

| 论文 | 字符 | 论文 | 字符 |
| --- | ---: | --- | ---: |
| paper:2609.29429 | 198,069 | paper:2609.29808 | 64,267 |
| paper:2609.28915 | 197,092 | paper:2609.29757 | 62,963 |
| paper:2609.30266 | 111,164 | paper:2609.28996 | 59,267 |
| paper:2609.30243 | 109,805 | paper:2606.15617 | 30,694 |
| paper:2609.30217 | 103,417 | paper:2501.13787 | 29,973 |
| paper:2609.29228 | 83,155 | paper:2609.29333 | 27,059 |
| paper:2609.30192 | 17,661 | paper:2609.29230 | 14,189 |
| paper:2609.28900 | 15,705 | paper:2609.30028 | 13,292 |

**随机 10 个 chunk 抽样**（`seed=20261018`，正文可读；表格/公式块仍不可读，见第 8 节）：

1. `paper:2609.29228` 第 94 块 — 表格（Edit Distance）
2. `paper:2609.29429` 第 199 块 — "…On the corrected labels, Open-Prompt-Injection moves from inverted to near-perfect ranking…"
3. `paper:2609.28900` 第 49 块 — 公式 + "(ii) Soundness. Let Bad be the event that Extract returns…"
4. `paper:2609.30217` 第 83 块 — 目录（Appendix Contents）
5. `paper:2609.30243` 第 131 块 — 表格（SATA/BFCL）
6. `paper:2609.28915` 第 71 块 — 目录（点线）
7. `paper:2609.29230` 第 65 块 — "…n-Level Loss, which normalizes the policy gradient over all active tokens in the batch rather than per sequence, elimi- nating length bias…"
8. `paper:2609.28900` 第 17 块 — "…kv with range{0,1} λ , which validates a decoded message…"
9. `paper:2609.29333` 第 155 块 — 表格（Table 24 continued）
10. `paper:2609.29333` 第 88 块 — "…summing to 10.0 points awarded in prose — the largest contradicted total in Table 7…"

## 6. 50 题重跑（新语料）

```powershell
$env:B_QA_CORPUS_DIR = 'D:\ICT\intel-data-b-colfix-20261018'
.\.venv\Scripts\python.exe tools\run_b_qa_eval.py --out artifacts\b_eval\formal_qa_results_20261018.json
```

| 指标 | 20261012 批次 | **20261018 重跑** | 要求 |
| --- | --- | --- | --- |
| 异常 / 超时 | 0 / 0 | **0 / 0** | 0 / 0 ✓ |
| 引用命中 | 97.22%（35/36） | **97.22%（35/36）** | 不低于 97.22% ✓ |
| 预期词命中 | 92.11%（35/38） | **92.11%（35/38）** | 不低于 92.11% ✓ |
| 拒答一致 | 84% | **84%（42/50）** | — |
| 引用可追溯 | 100% | **100%（229/229）** | — |
| P50 / P95 | 449.9 / 627.9 ms | **523.7 / 669.9 ms** | 记录 |

**逐题比对：50 题里 31 题的答案文本发生变化**（BQA-001/002/003/004/005/006/007/010/011/012/014/015/016/
017/019/020/021/023/025/026/028/029/030/031/032/034/040/044/047/048/049）。典型对照：

| 题 | 旧答案（layout 语料） | 新答案（修复后） |
| --- | --- | --- |
| BQA-001 | "This paper uses a high-quality dataset extracted in the To evaluate DistillGuard, we investigate the following three" | "**This paper presents DistillGuard, a novel NPM mali…**" |
| BQA-003 | "arXiv preprint arXiv:2310.18512, 2023." | "**CODETTA, a high-capacity steganographic protocol for independently deployed agents…**" |
| BQA-005 | "anomaly and does not fully model complex phe- orizes, rl generalizes: A comparative study of" | "**EAGER reduces average F1 from 30.79 to 22.61**" |

聚合命中率没变，是因为期望术语本来就能在标签标题里命中；**变的是答案正文**，
而人工判定看的正是正文。

## 7. 改了什么、没改什么

**改了**：`app/rag_corpus.py`（`_parse_pdf` 不再用 layout、`PARSER_VERSION` 升到 1.3）、
`tools/run_b_qa_eval.py`（新增 `B_QA_CORPUS_DIR` 覆盖，默认仍是旧目录）、
`tests/test_rag_corpus.py`（2 条新测试）。

**没改**：分块参数（`DEFAULT_CHUNK_CHARS` / `DEFAULT_OVERLAP_CHARS`）、检索与排序、
任何判定标准、1012 批次的旧产物、旧语料目录。

## 8. 局限

* **表格与公式仍不可读**：plain 抽取能把正文逐栏读出，但表格会变成一串数字（第 5 节抽样 1/5/9），
  公式会丢失上下标。它们不是"两栏交织"，但也无法直接引用——这部分只能靠不把它们当正文。
* `pypdf` 对部分 CFF Type1 字体报 `fontTools` 缺失警告（不影响正文抽取）。
* **B4 人工重判尚未进行**：`qa_human_score_20261018.json` 与 `qa_performance_20261018.json`
  需在人工判定后产出；在此之前页面仍显示 20261012 批次，
  报告引用必须写"20261012 批次、10-15 判定"，不能说成当前代码的成绩。