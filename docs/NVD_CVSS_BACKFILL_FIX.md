# NVD CVSS 回填缺口修复

**日期**：2026-10-05  
**背景**：B 任务 2026-10-04 关系金标准中发现 5 条漏检（FN），全部落在 `cvss` 维度。

## 1. 缺口是什么

`tools/backfill_nvd_poc.py` 的作用是：对**已经入库**的事件，用 NVD 快照补充来源字段。
但它当时只合并了 NVD 的 `Exploit` 引用到 `poc[]`，**完全丢弃了 `nvd_to_event()` 已经算出来的 CVSS**。

后果：一个经 OSV / MITRE / KEV 入库、自身没有 CVSS 的事件，永远拿不到 NVD 的 CVSS，
于是 `cvss` 关系维度对它没有任何可抽取内容 —— 这正是 B 定位到的 5 条漏检的根因。

## 2. 修了什么

| 文件 | 改动 |
| --- | --- |
| `app/storage.py` | 新增 `merge_event_cvss(event_id, records)`：按 `(source_id, vector)` 去重合并，不替换事件 |
| `tools/backfill_nvd_poc.py` | 在原有 `poc` 合并之外，同时合并 `cvss`；报告分别统计两者 |
| `tests/test_nvd_cvss_backfill.py` | 4 条测试：补入、幂等、跨来源同向量保留、事件不存在时不写入 |

去重键选择 `(source_id, vector)` 而不是 `vector`：同一条向量被不同上游各自公布时，
它们是两条可分别引用的证据，不应互相覆盖。

## 3. 实测结果

对 150 个本机 NVD 快照运行修复后的回填：

```
snapshot_files                 : 150
events_with_poc                : 1316   (poc_events_updated: 0，早已合并)
events_with_cvss              : 18968  (cvss_events_updated: 14)
cvss_events_unchanged_or_missing: 18954
events_updated_any             : 14
```

**14 个事件新获得了 CVSS**，此前它们只有 POC 被回填。

对 B 的 5 条漏检逐条复核（金标准期望向量 vs 库内实际向量）：

| 金标准 ID | 事件 | 结果 |
| --- | --- | --- |
| BREL-GOLD-FN-CV-0001 | CVE-2026-64849 | FOUND |
| BREL-GOLD-FN-CV-0002 | CVE-2025-62593 | FOUND |
| BREL-GOLD-FN-CV-0003 | CVE-2025-62593 | FOUND |
| BREL-GOLD-FN-CV-0004 | CVE-2026-33017 | FOUND |
| BREL-GOLD-FN-CV-0005 | CVE-2026-33017 | FOUND |

**5/5 全部命中**。其中 `CVE-2026-33017` 本机 NVD 快照中不存在（0 个文件命中），
改用按 CVE 定向请求 NVD API 补齐，返回 2 条 CVSS（4.0 / 3.1）并合并成功。

## 4. 遗留：分数要下一轮才更新

`artifacts/b_eval/relation_score_gold_20261004.json` 仍显示 `FN=5`，这是**正确且刻意保留的**：
它是 2026-10-04 那一刻的冻结快照。数据修好不等于分数自动变，还需要：

1. 重新运行 `tools/build_b_relation_candidates.py` 生成候选集；
2. 人工核验新出现的 5 条 cvss 候选（它们初始状态是 `pending_human_review`，不计入任何分母）；
3. 重新运行 `tools/score_b_relation_annotations.py --gold ...` 得到新分数。

在此之前，页面上显示的 Recall/F1 仍是 10-04 批次的诚实结果（Recall 90.38%），不能提前写成 100%。

## 5. 也不能忽略的边界

- 本次修复解决的是**链路丢弃 CVSS**的问题，不是「NVD 一定收录所有 CVE」。若某 CVE 连 NVD 都没有，
  系统仍然没有 CVSS，框架会把该关系留在缺口里而不是编造。
- `cvss` 只是四个受评维度之一；`poc`、`asset_assessment` 仍按 B 的口径单列。
