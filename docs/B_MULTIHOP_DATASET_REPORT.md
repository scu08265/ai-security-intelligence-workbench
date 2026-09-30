# B 任务 · 跨文档与多跳候选题集

| 项 | 值 |
| --- | --- |
| 日期 | 2026-09-30 |
| 文件 | `evaluation/b_multihop_candidates.json`（31 条候选） |
| 生成器 | `tools/build_b_multihop_candidates.py`（从真实证据生成，可复现） |
| 校验 | `tests/test_b_multihop_candidates.py`（8 项，全部通过） |

## 1. 结论先说

**已构建 31 条候选题，全部为候选，0 条已人工验收。**

| 类型 | 数量 | 是否等于"多跳推理" |
| --- | ---: | --- |
| `two_hop`（事件→组件→文档） | **10** | 不是。第二跳是"组件名出现在文档文本中"，属**字符串共现**，不代表论文对该事件作出论断 |
| `cross_document`（同一术语跨 ≥2 篇文档） | **21** | 不是。这只证明检索层能覆盖多篇文档 |

**系统当前不具备多跳推理能力**：只有 `known_exploited` 一种显式关系谓词，
没有实体/关系抽取，也没有路径搜索。因此本数据集**不是**"已实现多跳"的证据。

## 2. 每条题目的必备字段

`question_id` / `chain_type` / `question` / `answer_points` / `documents` / `entities` /
`edges`（每条边含 `from`、`relation`、`to`、`evidence`）/ `reasoning_path` /
`required_evidence` / `evidence_complete` / `verification_status` / `notes`。

每条边的证据要么是**真实存在的 `chunk_id`**（含 `document_key` 与字符坐标），
要么是**真实存在的事件字段**（含 `event_id` 与来源 ID）。

## 3. 真实证据校验（自动，实测）

`tests/test_b_multihop_candidates.py` 对全部 31 条、逐条边校验：

| 校验 | 结果 |
| --- | --- |
| 每条边都带证据且类型已知 | ✅ |
| `chunk_id` 在库中存在 | ✅ |
| 边的 `document_key` 与分块归属一致 | ✅ |
| `char_end - char_start == len(分块文本)` | ✅ |
| `extracted_text[char_start:char_end]` 与该分块文本逐字一致 | ✅ |
| `event_field` 证据指向的事件存在 | ✅ |
| `cross_document` 确实跨 ≥2 篇文档 | ✅ |
| `two_hop` 含 1 条事件边 + ≥1 条分块边，且路径节点 ≥3 | ✅ |
| 问题文本无重复、全部 `pending_human_review` | ✅ |

## 4. 为什么不是 30 条已验证多跳题

| 缺口 | 事实 |
| --- | --- |
| 关系谓词单一 | 全库 26 条关系边，谓词只有 `known_exploited`，客体只有 "CISA KEV catalog" |
| 没有关系抽取 | `app/knowledge_views.py` 明确写着"不推断边"；全仓库无实体/关系抽取实现 |
| 可用的 2 跳资源有限 | 事件组件中只有 `vllm`(9) 与 `ray`(1) 能在 RAG 文档中找到对应提及，共 10 个事件 |
| 不可用的组件 | `open-webui`、`mlflow`、`langflow` 等组件在语料文档中**零出现**，无法构链 |

**因此没有拼凑虚假推理链**：`cross_document` 类题目如实标注为"跨文档检索"，
`two_hop` 类题目如实标注"第二跳是共现而非论断"。

## 5. schema 扩展建议（未实施，需单独授权）

若要表达真实多跳关系，建议新增独立关系标注文件（**不改数据库 schema**）：

```json
{
  "edge_id": "EDGE-0001",
  "subject": "<实体或文档>",
  "predicate": "<关系类型>",
  "object": "<实体或文档>",
  "evidence": {"chunk_id": "...", "document_key": "...", "char_start": 0, "char_end": 100},
  "verified": false,
  "verified_by": null
}
```

只有在积累到足够多 `verified: true` 的边之后，才具备构建真实多跳题的条件。

## 6. 未确认事项

- 31 条候选**全部未经人工核验**；`two_hop` 的"论文是否真的讨论该事件"未确认。
- 系统在这 31 题上的实际作答表现**未逐题评测**（多跳题在 50 题集中另有 2 道，结果见
  `docs/B_FORMAL_QA_EVAL.md`：两道都在无推理链的情况下返回了主题相关引用）。
