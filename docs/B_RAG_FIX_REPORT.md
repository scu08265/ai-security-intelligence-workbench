# B 任务 · RAG 问答缺陷修复报告（D-1 / D-2 / D-4）

| 项 | 值 |
| --- | --- |
| 日期 | 2026-09-30 |
| 仓库 | `D:\ICT\ai-security-intelligence-workbench-git` @ `feat/b-evaluation` |
| 数据目录 | `D:\ICT\intel-data-b`（本轮**零写入**） |
| 状态 | **已实际执行**：代码修复 + 自动化回归 + 数据库副本实测 |

## 1. 修改前基线（实测）

| 项 | 值 |
| --- | --- |
| Git 分支 | `feat/b-evaluation` |
| 已跟踪改动 | 仅 `app/evaluation.py`（2 行，早前已批准） |
| 暂存区 | 空 |
| 数据库大小 / SHA-256(前32) | 8,183,808 B / `4095a5b1ff836f70baf5552304aac95f` |
| RAG 文档 / 版本 / 分块 | 22 / 22 / 3639 |
| `full_text=fulltext` | 16 篇 |
| 备份 | `D:\ICT\intel-data-b-backups\intel-before-phaseB-20260930-094325.sqlite` |

## 2. D-1：52.4% 分块被静默丢弃

### 根因

`app/rag.py::chunks_from_records` 先用 `_text()`（内部 `.strip()`）归一文本，
再用**归一后的长度**校验 `char_start` / `char_end`：

```python
body = _text(item.get("text") or item.get("quote"))      # 已 strip
end = int(item.get("char_end") if ... else start + len(body))
if start < 0 or end != start + len(body):                 # 用 strip 后的长度比区间
    continue                                              # 静默丢弃
```

因此**任何以换行或空白结尾的分块**都会被判为"区间不一致"而丢弃。

### 实测证据

- 数据库层面 **3639 / 3639** 个分块满足 `char_end - char_start == len(原始文本)`，
  **落库数据完全一致**；问题只在校验逻辑。
- 被丢弃的 1906 个分块全部由"首尾空白"触发。样例：区间 1295..2291、原始长度 996、
  strip 后 995，正文以 `...lation.\n` 结尾。
- 逐文档可见率：16 篇 arXiv 论文 **28.4%–47.5%**；`eu_ai_act` 49.5%；
  `nist_news` / `owasp_genai` / `nist_ai_rmf` / `mitre_atlas` 为 100%。

### 修复

`app/rag.py::chunks_from_records`：**保留既有 `text or quote` 回退语义**，
但长度校验与 `Chunk.text` 一律使用**存储原文**；空文本判定仍用 strip 结果。

```python
raw_text = item.get("text") or item.get("quote")   # 保留原回退行为
text = "" if raw_text is None else str(raw_text)
body = _text(raw_text)                             # 仅用于"是否有内容"的判断
...
if start < 0 or end != start + len(text):          # 用原文长度校验区间
    continue
chunks.append(Chunk(..., text=text, ...))          # 引用区间与正文严格对应
```

### 效果（实测，数据库副本）

| 指标 | 修复前 | 修复后 |
| --- | ---: | ---: |
| `chunks_from_records` 可见分块 | 1733 / 3639（47.6%） | **3639 / 3639（100%）** |

## 3. D-2：英文专名 + 中文问句得 0 命中

### 根因

`app/rag.py::retrieve_chunks` 的守卫：

```python
if not exact_identifier and len(unique_query) >= 4 and len(matched) < 2:
    continue
```

中文问句被切成大量在英文语料中零命中的二字词元，使 `unique_query` 迅速变大，
而真正匹配的只有一个英文专名，整条查询被丢弃。

### 实测证据（修复前）

| 查询 | 词元 | 命中 |
| --- | --- | ---: |
| `DistillGuard` | `[distillguard]` | 77（KeywordIndex）/ 12（RAG 层） |
| `DistillGuard 是做什么的？` | `[distillguard, 是做, 做什, 什么, 么的]` | **0** |
| `OllamaDrama 蜜罐观察到了什么？` | `[ollamadrama, 蜜罐, …]` | **0** |
| `哪些文档讨论了 AUROC？` | `[auroc, 哪些, 些文, …]` | **0** |

### 修复

**不删除守卫、不写专名特例**，而是把"≥2 个匹配"的要求细化为"单一匹配必须**具有区分度**"：

```python
if not exact_identifier and len(unique_query) >= 4 and len(matched) < 2:
    only_match = matched[0] if len(matched) == 1 else None
    if only_match is None or df.get(only_match, 0) > max(1, len(chunks) // 20):
        continue
```

阈值 `语料量/20`（3639/20 = 181）有实测支撑：

| 词 | 文档频率 | 占比 | 是否放行 |
| --- | ---: | ---: | --- |
| `distillguard` | 21 | 0.58% | ✅ |
| `ollamadrama` | 11 | 0.30% | ✅ |
| `derm7pt` | 7 | 0.19% | ✅ |
| `preemption` | 79 | 2.17% | ✅ |
| `auroc` | 153 | 4.20% | ✅ |
| `ai` | 1301 | 35.75% | ❌ 拒绝 |
| `model` | 729 | 20.03% | ❌ 拒绝 |
| `security` | 505 | 13.88% | ❌ 拒绝 |

### 效果（实测，数据库副本）

| 查询 | 修复前命中 | 修复后命中 | 命中文档 |
| --- | ---: | ---: | --- |
| `DistillGuard` | 12 | 12 | paper:2609.28996 |
| **`DistillGuard 是做什么的？`** | **0** | **12** | paper:2609.28996 |
| **`OllamaDrama 蜜罐观察到了什么？`** | **0** | **11** | paper:2609.29757 |
| `Codetta 是什么？` | — | 8 | paper:2609.28900 |
| `FoobarGuard 是做什么的？`（不存在） | 0 | **0** | — |
| `asdf qwerty`（无意义） | 0 | **0** | — |
| `DISTILLGUARD???` | — | 12 | 与裸词一致 |

## 4. D-4：拒答文案与文档引用并存

### 根因

`app/intelligence.py::answer_question` 中结构化事件路径与 RAG 文档路径**并行**：

```python
rag_result = answer_with_rag(_text(question), events or [], chunks=rag_chunks)
def with_rag(payload):
    payload["rag"] = rag_result
    payload["document_citations"] = rag_result["citations"]   # 无条件挂上引用
    ...
if not selected:
    return with_rag({"answer": "现有证据中未找到可匹配的事件，无法可靠回答。...", ...})
```

事件路径拒答时，RAG 命中的真实引用仍被挂上，形成"拒答文案 + 真实引用"。

### 修复（`app/intelligence.py::with_rag`，最小改动、不改公开字段）

当**事件路径无任何证据**、而**文档路径确有引用且未拒答**时，以文档证据为准：
替换答案、追加一条 trace、追加一条 limitation；其余情况一律不动。

```python
has_event_evidence = bool(payload.get("related_event_ids")) or bool(payload.get("citations"))
if (not has_event_evidence and not rag_result.get("refused")
        and rag_result.get("citations")):
    payload["answer"] = rag_result.get("answer") or payload.get("answer")
    payload["trace"] = ... + [{"action": "answer_from_document_evidence", ...}]
    payload["limitations"] = ... + ["结论来自版本化文档分块；…引用以文档为准"]
```

返回字段一个未增未减，`answer / citations / rag / document_citations` 的类型与结构保持不变。

### 效果（实测）

| 情形 | 修复前 | 修复后 |
| --- | --- | --- |
| 事件拒答 + 文档有证据 | 拒答文案 + 5–6 条引用（**矛盾**） | 文档答案 + 引用 + trace + limitation |
| 无关问题、无文档 | 拒答、无引用 | **不变** |
| 文档检索无结果 | 拒答、无引用 | **不变** |
| 事件路径已有答案 | 答案 + 引用 | **不变**（答案不被覆盖，引用不被清空） |

**矛盾用例数：修复前 2 条 → 修复后 0 条。**
（订正：`docs/B_QA_SMOKE_EVAL.md` 初稿写"3 条用例"，按实际数据应为 **2 条**：
`term-prompt-injection` 与 `cross-doc-3`。该文档已同步订正。）

## 5. 新增回归测试（全部离线、可重复）

| 文件 | 数量 | 覆盖 |
| --- | ---: | --- |
| `tests/test_rag_chunk_contract.py` | 29 | D-1：无/单/多换行、首尾空白、`text→quote` 回退、非法区间拒绝、空白文本拒绝、中英混合、批量无重复 |
| `tests/test_rag_mixed_language_query.py` | 18 | D-2：裸专名、专名+中文问句、不存在专名、无意义短查询、大小写/标点/重复词、纯英文、纯中文扩展、高频词拒绝 |
| `tests/test_rag_answer_citation_consistency.py` | 8 | D-4：拒答改判、拒答保持、引用可追溯、事件答案不被覆盖、引用不被清空、返回结构不变 |

`test_rag_chunk_contract.py` 与 `test_rag_answer_citation_consistency.py` **完全不触碰数据库**；
`test_rag_mixed_language_query.py` 在 `tmp_path_factory` 生成的**数据库副本**上运行。

## 6. 实测结果汇总

| 命令 | 结果 |
| --- | --- |
| `pytest tests\test_rag_chunk_contract.py -q` | **29 passed** |
| `pytest tests\test_rag_mixed_language_query.py -q` | **18 passed** |
| `pytest tests\test_rag_answer_citation_consistency.py -q` | **8 passed** |
| 6 个 B 测试文件合计 | **95 passed** |
| 全量 `pytest -q` | **373 passed**（318 基线 + 55 新增），0 failed，0 skipped |

## 7. 13 条问答冒烟对照（隔离副本，真实库零写入）

| 用例 | 引用数（前→后） | 覆盖文档数（前→后） | 仍含拒答文案（前→后） |
| --- | --- | --- | --- |
| base-fact-events | 1 → 6 | 1 → **2** | False → False |
| base-fact-cve | 0 → 0 | 0 → 0 | False → False |
| term-prompt-injection | 6 → 6 | 1 → 1 | **True → False** |
| paper-single-1 | **0 → 4** | 0 → 1 | **True → False** |
| paper-single-2 | **0 → 4** | 0 → 1 | **True → False** |
| cross-doc-1 | 6 → 6 | 1 → 1 | False → False |
| cross-doc-2 | **0 → 5** | 0 → **2** | **True → False** |
| refuse-offtopic | 0 → 0 | 0 → 0 | True → **True**（拒答保持） |
| refuse-secret | 0 → 0 | 0 → 0 | True → **True**（拒答保持） |
| citation-eu-ai-act | 0 → 0 | 0 → 0 | True → True（**未改善**） |
| cross-doc-3 | 5 → 5 | 1 → **2** | **True → False** |
| term-kernel-evidence | 6 → 6 | 1 → 1 | False → False |
| multiturn-followup | 0 → 0 | 0 → 0 | True → True（**未改善**） |

引用可追溯性：修复后所有引用（`referenced` 计数）**100% 可按 `chunk_id` 取回**。
**引用内容是否支持结论仍需人工核验**，本报告不声称已完成该核验。

### 两个仍未改善的用例（既有局限，非本轮缺陷）

1. **`citation-eu-ai-act`**：问题为纯中文（"欧盟 AI 法案对透明度有什么要求？"），
   `app/rag.py::terms()` 的中英扩展表只有 7 条，没有"透明度/要求/欧盟/法案"的映射，
   因此检索层得到 0 命中。属**词典覆盖不足**，需要扩充扩展表或改用跨语言检索。
2. **`multiturn-followup`**：RAG 路径只用 `_text(question)` 原文检索，
   不继承会话上下文，所以"它的检测方法有什么局限？"里没有任何可匹配词汇。
   要修需要把对话上下文注入 RAG 查询构造——属**流程变更**，本轮未做。

## 8. D-3 评估（不改架构）

### 实测（6 道有真实证据的跨文档问题）

| 查询 | 检索命中 | 检索覆盖文档 | 引用覆盖文档 | 答案是否综合多文档 |
| --- | ---: | ---: | ---: | --- |
| AUROC | 12 | 2 | 2 | ❌ |
| kernel-level | 12 | 2 | 2 | ❌ |
| NIST AI Risk Management Framework | 12 | 2 | 2 | ❌ |
| risk management | 12 | 2 | 2 | ❌ |
| transparency obligations | 12 | 1 | 1 | ❌ |
| multi-agent | 12 | 2 | 2 | ❌ |

### 限制来源定位

- **检索阶段**：不是瓶颈——`retrieve_chunks(limit=12)` 返回的命中覆盖 2 个文档。
- **引用装配**：`assemble_context(max_chunks=6)` 保留了这 2 个文档的引用。
- **答案生成阶段**：**瓶颈在这里**。`answer_with_rag(generator=None)` 的 answer 由
  `citations[:3]` 的原文 quote 用 `"- "` 拼接而成，没有任何跨文档事实组合逻辑。

### 结论与建议

**修复后引用层已经能够返回来自 2 个不同文档的证据**（修复前恒 ≤1），
但**系统仍不具备跨文档综合能力**——答案只是并列的原文摘录。

若要实现真正的跨文档综合，需要改动共享问答流程（新增加 `generator` 或综合步骤），
**本轮未实施**。建议单独授权后按以下设计推进：

1. 在 `answer_with_rag` 中引入可选的综合步骤（现有 `generator` 参数已是预留接口）；
2. 综合结果必须逐句绑定 `chunk_id`，无引用即拒答；
3. 增加"多文档综合"专项评测集（每题标注所需文档、事实与证据），按跳数分层报告。

## 9. 未确认事项

- **引用内容是否支持结论**：未做人工核验（只验证了 ID 可追溯与原文切片一致）。
- 13 条冒烟题由本任务编写，**不是人工核验金标准**，不得当作正式准确率。
- 未评估重排器；22 个文档未逐个人工抽读。
- RAG 路径下的旋转文本 / `fontTools` 缺失影响未量化。
- 未测试 `/api/chat` 的 HTTP 层（直接调用 `agents.answer`）。

## 10. 本轮未做的事

- 未修改任何 schema，未执行数据库迁移
- 未运行真实采集、补证、资产研判、定时任务、自愈或 `/api/seed`
- 未删除任何快照、文档或分块
- 未执行任何 Git 写操作
- 未安装任何依赖
- 未把自动生成的答案当作人工核验金标准
