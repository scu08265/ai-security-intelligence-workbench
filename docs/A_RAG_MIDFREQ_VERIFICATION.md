# A1 关闭记录：中频词检索回归

任务书 2026-10-12 的 A1 要求"关闭这条线"，并且明确**不要**按调阈值的方向改。本文件是收口证据。

## 1. 结论

问题**不在** `max(1, len(chunks) // 10)` 这个区分度守卫——`kernel-level`（df 9.0%）本来就能通过守卫
并正常命中。真正失败的只有 `multi-agent` 那条，输在**排序**：`论文` 会扩展成
`paper / study / arxiv`，旧代码把每个同义词各自计一份分，于是一篇只写了 "paper" 的论文能拿到约
10 分，而真正的主题词 `multi-agent` 只有约 2.5 分，把真正讨论 multi-agent 的那篇挤出前 8。

修复已在 `main`（`9ff738323d`，"count a Chinese phrase's synonym group once when ranking
retrieval"）：一个中文短语的同义词组按**一个概念**计分，取其中最强的一个成员。

## 2. 三件事的完成情况

### 2.1 废弃 `fix/a-rag-midfreq-regression`

该分支当时只停在 `1fb7662`（等于当时的 `main`），**零独有提交**，已删除。全程没有按"调阈值"
的方向改过任何代码。

### 2.2 有语料机器上的复验

语料已交付并核验到 `D:\ICT\intel-data-b`：

```
intel.sqlite   8,183,808 bytes
sha256         4095a5b1ff836f70baf5552304aac95f7eab5ee95fb3a58c45768e3478254285
压缩包内 47 个文件对照自带 MANIFEST.sha256 全部通过
```

命令一：

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_rag_mixed_language_query.py -q
```

```
30 passed in 12.23s
```

（语料到位前是 `10 passed / 20 skipped`，现在 20 条依赖语料的用例全部真跑并通过。）

命令二：

```powershell
.\.venv\Scripts\python.exe tools/diagnose_rag_midfreq.py --corpus-dir D:\ICT\intel-data-b
```

```
3. verdict
  kernel-level 在哪些文档中出现？    -> passes
  multi-agent 主题出现在哪些论文中？ -> passes
```

两条都是 `-> passes`，不再是 `-> retrieval`。细节：

| 用例 | expansion-injected | 单命中 df | 守卫判定 | 期望文档 |
| --- | --- | --- | --- | --- |
| `kernel-level 在哪些文档中出现？` | none | 328（9.0%） | `PASSES` | `paper:2609.28915` 被引用 |
| `multi-agent 主题出现在哪些论文中？` | `arxiv / paper / study` | 293（8.1%） | `PASSES` | `paper:2609.28900` 被引用（修复前被挤出前 8） |

全量测试（交付机）：

```
675 passed, 4 skipped, 1 warning in 84.38s
```

剩余 4 条跳过与本项无关，是 B1 那两个尚未交付的衍生副本：
`D:\ICT\intel-data-b-cvss-20261006`（3 条）与 `D:\ICT\intel-data-b-poc-20261002`（1 条）。

> 复跑提示：在没有 `D:\ICT` 写权限的环境里跑全量测试，`tests/test_rag_retrieval_b_task.py`
> 会有 30 条报 `sqlite3.OperationalError: unable to open database file`。原因是该文件
> （第 80-82 行）把 `config.DB_PATH` **直接**指向 `D:\ICT\intel-data-b\intel.sqlite`，
> 而 `app/storage.py:366` 的 `PRAGMA journal_mode=WAL` 需要在语料目录里建 `-wal` / `-shm`。
> 这不是代码缺陷，给该目录写权限即恢复全绿；`test_rag_mixed_language_query.py` 因为先复制到
> 临时目录，所以不受影响。

### 2.3 走查 `app/rag.py`：没有别的调用点依赖旧的逐词计分

改动只落在 `retrieve_chunks` 的 BM25 打分循环：

- 新增 `expansion_terms()`，全仓库只有 `app/rag.py:342` 一个调用点；
- 注入的同义词累计成 `injected_score = max(...)`，每个分块只加一次；
- `terms()` 本身**一行未动**，因此所有消费它的地方行为完全不变：
  `_answer_sentence_candidates` 的句子重叠打分、`required_terms` 集合过滤、
  `app/intelligence.py:332` 的问句长度启发式、`tools/diagnose_rag_midfreq.py` 与全部测试。

唯一值得后续留意的地方：`_answer_sentence_candidates`（`app/rag.py:509-525`）仍按
`len(overlap)` 计分，即"一个中文短语扩展出的多个同义词"在**选句**这一层仍然各算一份。
它不参与检索排序、不是本次回归的原因、改动前后行为一致；若将来发现答案选句偏向
paper/study/arxiv，这里是第一个要看的地方。

## 3. A5：阈值未被触碰

`app/rag.py:387` 仍是

```python
if only_match is None or df.get(only_match, 0) > max(1, len(chunks) // 10):
```

`git log -1 -S "len(chunks) // 10" -- app/rag.py` 指向 `32ad7ed`（B 在该提交里连同测试一起
标定的原始阈值），本次修复没有改动它。
