# B 任务 · RAG 语料清单与检索评测

| 项 | 值 |
| --- | --- |
| 日期 | 2026-09-30 |
| 语料 | `D:\ICT\intel-data-b`，22 个文档 / 22 个版本 / 3639 个分块 |
| 测试文件 | `tests/test_rag_retrieval_b_task.py`（自动化，30 项，全部通过） |
| 状态 | **已实际执行**（本地检索，只读，无网络） |

## 1. 语料清单（22 个文档）

### 1.1 arXiv 论文全文（16 篇，2169 分块）

| document_key | 标题 | 分块 | 正文（字节） | 适用性 |
| --- | --- | ---: | ---: | --- |
| paper:2609.30028 | How does Adversarial Influence Scale in Multi-Agent Systems | 94 | 73,444 | 有效 |
| paper:2501.13787 | Parameter-Efficient Fine-Tuning for Foundation Models | 170 | 136,214 | 有效（含 1 个控制字符分块） |
| paper:2609.29333 | Where LLM Graders Succeed and Break | 185 | 144,518 | 有效 |
| paper:2609.29429 | Just Ask Jev: Reinforcement Learning for Calibrated Decisions | 248 | 195,581 | 有效 |
| paper:2609.29230 | EAGER: Enhancing Generative Event Extraction | 116 | 92,095 | 有效 |
| paper:2609.30192 | SAGE: Mitigating Long-Horizon Reasoning Biases | 123 | 96,835 | 有效 |
| paper:2609.30217 | Instrumental Monitor Evasion Emerges Under Ordinary Task Pressure | 136 | 103,441 | 有效 |
| paper:2609.28996 | DistillGuard: Malicious NPM Package Detection | 77 | 59,661 | 有效 |
| paper:2606.15617 | NeRD: Neuro-Symbolic Rule Distillation | 37 | 26,729 | 有效（第 1 页有旋转文本警告） |
| paper:2609.28915 | On the Effectiveness of Kernel-Level Evidence for Agent Security | 249 | 196,856 | 有效 |
| paper:2609.28900 | Codetta: High-Capacity, Keyless, Undetectable Multi-Agent | 190 | 150,532 | 有效 |
| paper:2609.29228 | Towards An LLM-Driven Unified Conversion Framework | 107 | 79,049 | 有效 |
| paper:2609.30266 | LLM Agents Can Easily Tamper With Their Own Traces | 139 | 108,182 | 有效 |
| paper:2609.29757 | OllamaDrama: Honeypot to Measure ... | 83 | 61,175 | 有效 |
| paper:2609.29808 | Hard Stop: Kernel-Level Preemption and Containment | 79 | 62,473 | 有效 |
| paper:2609.30243 | JevOut: Natural Context Can Flip Decision Models | 136 | 106,501 | 有效 |

### 1.2 已采集来源文档（6 个，1470 分块）

| document_key | 来源类型 | 分块 | 正文（字节） | 适用性 |
| --- | --- | ---: | ---: | --- |
| official:eu_ai_act | 官方 PDF（法规全文） | 849 | 607,892 | **有效，且是唯一的完整法规文本** |
| source:security_blog | RSS 聚合（**整份 feed，非单篇**） | 290 | 133,875 | 可用于主题检索，粒度粗 |
| source:nist_news | RSS 聚合（**整份 feed，非单篇**） | 243 | 16,752 | 同上 |
| source:owasp_genai | HTML 单页正文 | 64 | 10,117 | 有效 |
| source:nist_ai_rmf | HTML 单页正文 | 23 | 3,480 | 篇幅较小 |
| source:mitre_atlas | HTML（JS 渲染） | **1** | **14** | **低质量，检索价值为零（已知缺陷）** |

**标注事项**

- **MITRE ATLAS 为低质量文档**：正文实际内容仅为 `MITRE ATLAS™`，被
  `tests/test_rag_retrieval_b_task.py::test_known_low_quality_document_is_flagged_by_its_size` 固定记录。
  **本阶段未删除该文档**；建议后续排除或改用非 JS 端点修复。
- **RSS 聚合文档不是单篇文章**：`security_blog` 与 `nist_news` 各以整份订阅列表为一个文档，
  不能当作单篇报道引用。
- **旋转文本警告**：至少 2606.15617 与 2501.13787 第 1 页存在，抽取可能不完整。
- **控制字符分块**：28 个（见 `B_PAPER_FULLTEXT_REPORT.md` 第 5.3 节）。

## 2. 检索回归测试（19 条用例，全部通过）

测试文件：`tests/test_rag_retrieval_b_task.py`。期望值**全部取自语料真实内容**，
每个 `must_include` 都先在真实语料上验证过确实存在该术语。

| 用例 | 查询 | 必须命中的文档 | 命中数 | 覆盖文档数 |
| --- | --- | --- | ---: | ---: |
| single-title | Parameter-Efficient Fine-Tuning | paper:2501.13787 | 227 | 10 |
| single-sysname | DistillGuard | paper:2609.28996 | 77 | 1 |
| single-sysname2 | OllamaDrama | paper:2609.29757 | 83 | 1 |
| single-term | preemption | paper:2609.29808 | 79 | 1 |
| control-char-adj | GeLU | paper:2501.13787 | 3 | 1 |
| single-acronym | Derm7pt | paper:2606.15617 | 9 | 1 |
| non-paper-source | European Union AI Act | official:eu_ai_act | 500 | 1 |
| single-word | grader | paper:2609.29333 | 195 | 4 |
| cross-auroc | AUROC | paper:2609.29429, paper:2609.28915 | 169 | 2 |
| cross-kernel | kernel-level | paper:2609.28915, paper:2609.29808 | 328 | 2 |
| cross-rl | reinforcement learning | paper:2609.29429, paper:2609.29230 | 500 | 19 |
| cross-multiagent | multi-agent | paper:2609.28900, paper:2609.30028 | 293 | 6 |
| cross-malicious | malicious package | paper:2609.28996, source:security_blog | 226 | 12 |
| cross-transparency | transparency obligations | official:eu_ai_act, source:security_blog | 173 | 6 |
| cross-nistrmf | NIST AI Risk Management Framework | source:nist_ai_rmf, official:eu_ai_act | 500 | 14 |
| late-eu-ai-act | Schengen | official:eu_ai_act | 3 | 1 |
| late-paper-a | paraphrased | paper:2609.28915 | 7 | 3 |
| late-paper-b | benign | paper:2609.29429 | 88 | 10 |
| mixed-source-type | risk management | official:eu_ai_act, source:nist_ai_rmf | 500 | 19 |

**测试结果：`30 passed`**（19 条用例 + 8 条跨文档重复断言 + 3 条专项测试）。
命令：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_rag_retrieval_b_task.py -q -p no:cacheprovider
```

## 3. 跨文档检索检查（8 组）

用于"跨文档"判定的 8 组主题（AUROC / kernel-level / reinforcement learning / multi-agent /
malicious package / transparency obligations / NIST AI RMF / risk management）**均实际命中 ≥ 2 个不同
`document_id`**，由 `test_cross_document_queries_span_multiple_documents` 断言。

**必须区分清楚：**

- ✅ **检索层**确实会返回来自多个文档的分块。
- ❌ 这**不等于**系统完成了跨文档推理。检索层只是把多个文档的命中并列返回；
  真正的跨文档推理需要在问答层把不同文档的事实**组合**成新结论，那是另一件事。
- ⚠️ 在同一文档内命中多个分块（例如 `Parameter-Efficient Fine-Tuning` 命中 227 条但只覆盖 10 个文档）
  与"跨文档"是两回事，本报告不做混同。

## 4. 检索层的已知边界

1. **词法器是关键词 BM25，不是嵌入检索**：`app/rag_corpus.py::KeywordIndex` 与
   `app/rag.py::retrieve_chunks`。同义改写、跨语言查询的召回能力有限。
2. **中文提问 vs 英文语料**：`app/rag.py::terms()` 只有一张小型中英扩展表（7 条），
   大部分中文问句词元（如"欧盟""透明度""要求"的二字切分）无法匹配英文正文。
3. **`retrieve_chunks` 的 `len(matched) < 2` 守卫**：当查询词元数 ≥4 且只匹配到 1 个词元时，
   该分块被丢弃。因此"一个英文专名 + 中文疑问句"的提问会得到 0 命中（详见 `B_QA_SMOKE_EVAL.md`）。

## 5. 未确认事项

- 未对 22 个文档逐个人工抽读，**各文档内容质量未做人工核验**；上表"适用性"仅基于
  分块数、正文长度、解析警告与控制字符的机器判定。
- 未评估重排器（reranker）效果；现有链路使用默认关键词排序。

---

# 修复后更新（2026-09-30，D-1 / D-2 已修）

上文第 4 节记录的边界是**修复前**的状态，保留原样。修复详情见 `docs/B_RAG_FIX_REPORT.md`。

## 更新 1 · D-1 修复后，语料可见率从 47.6% 提升到 100%

`app/rag.py::chunks_from_records` 原先用 `.strip()` 后的长度校验原始字符区间，
导致所有以换行结尾的分块被丢弃。修复后改为用**存储原文**校验并保留原文。

| 指标 | 修复前 | 修复后 |
| --- | ---: | ---: |
| `chunks_from_records` 可见分块 | 1733 / 3639（47.6%） | **3639 / 3639（100%）** |
| arXiv 论文文档可见率 | 28.4%–47.5% | **100%** |

> 注意：本节第 2 节的 19 条检索用例测的是 `app/rag_corpus.search`（`KeywordIndex`），
> 该路径不受 D-1 影响，因此那些期望值**无需修改**，修复后仍全部通过。

## 更新 2 · D-2 修复后，中英混合查询可用

| 查询 | 修复前 | 修复后 |
| --- | ---: | --- |
| `DistillGuard` | 12 | 12 → paper:2609.28996 |
| `DistillGuard 是做什么的？` | **0** | **12** → paper:2609.28996 |
| `OllamaDrama 蜜罐观察到了什么？` | **0** | **11** → paper:2609.29757 |
| `FoobarGuard 是做什么的？`（不存在） | 0 | **0**（未引入误命中） |

数据依据：阈值取"文档频率 ≤ 语料量/20"，`distillguard`=21、`ollamadrama`=11、
`derm7pt`=7 通过，而 `ai`=1301、`model`=729、`security`=505 仍被拒绝。

## 更新 3 · 仍然存在的检索边界（未修）

| 边界 | 说明 |
| --- | --- |
| 中英扩展词典只有 7 条 | 纯中文问句（如"欧盟法案对透明度的要求"）无对应英文词元，仍为 0 命中 |
| RAG 路径不继承会话上下文 | 多轮追问（"它的…"）在 RAG 侧没有任何可匹配词元，仍为 0 命中 |
| 关键词检索而非嵌入检索 | 同义改写、跨语言召回能力有限，未变 |
