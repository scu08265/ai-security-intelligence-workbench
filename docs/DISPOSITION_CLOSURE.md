# 处置闭环（disposition closure loop）

**目标**：在“发现 → 研判 → 优先级 → 处置建议”之后补齐“登记处置 → 系统复测 → 关闭或回退”，让风险从数字变成可追溯的闭环。

## 1. 为什么需要它

`app.intelligence.assess_asset` 只能回答“这个资产是否受影响”，不记录谁在处理、什么时候处理、有没有真的修好。组员 B 的 `tools/asset_disposal_advisor.py` 只输出建议，报告也明确写了“本文件是处置建议，不是执行记录”。因此系统此前只有诊断，没有病历本。

## 2. 状态机

| 状态 | 含义 | 能否关闭 |
| --- | --- | --- |
| `open` | 已发现，尚未登记处置 | 否 |
| `in_progress` | 已指派，处理中 | 否 |
| `fixed` | 已修复，等待系统复测 | 否 |
| `verified` | 系统复测通过，已关闭 | 是 |
| `accepted` | 接受风险，记录决策 | 计入处置完成，但不代表风险消失 |

规则：

- 进入 `in_progress` 及之后的状态必须填写处置人；
- `verified` 必须由系统重新执行 `assess_asset`；
- 复测后资产仍命中受影响区间，则**降级为 `fixed`**，并保存失败复测记录，不允许人工声明关闭；
- 原始 `assessments.status` 永不被处置记录覆盖，`affected` 事实长期保留。

## 3. 存储与证据

新增表 `assessment_dispositions`，主键 `(event_id, asset_id)`，记录：`status`、`assignee`、`note`、`evidence_ids`、`version_before`、`version_after`、`opened_at`、`updated_at`、`closed_at`、`verification`、`doc`。

`opened_at` 首次登记后不再变化，因此可以计算平均关闭时长。`verification` 保存复测前后的研判状态、原因和结论，作为审计证据。

## 4. 指标口径

`GET /api/dispositions/metrics` 与 `/api/competition/scorecard` 的 `disposition` 字段：

- `high_priority_total`：`assessments.status=affected` 且 `priority ∈ {critical, high}` 的结论数；
- `high_priority_closed`：上述结论中状态为 `verified` 或 `accepted` 的数量；
- `closure_rate = high_priority_closed / high_priority_total`；分母为 0 时返回 `null`，不返回 0；
- `verified_rate`：只统计系统复测通过的关闭；
- `mean_time_to_close_hours`：仅统计同时有 `opened_at` 与 `closed_at` 的记录，样本为空时为 `null`；
- `status_breakdown`：27 条高优先级结论在各状态上的分布。

当前真实数据：高优先级 27 条，已关闭 0 条，闭环率 0%，全部为 `open`。这是尚未登记的客观状态，不是系统缺陷。

## 5. 使用方式

1. 在“最终结论与处置清单”里点击某条结论的“登记处置”；
2. 填写处置人、处置前/后版本、处置说明；
3. 状态选择“已修复待复测”或“已复测关闭”；
4. 选择“已复测关闭”时，系统自动重新研判该资产：
   - 版本已不命中受影响区间 → `verified`，记录关闭时间；
   - 仍命中 → 保持 `fixed`，保存失败复测结论并提示。

## 6. 与赛题能力的关系

- 保留客观性：原始受影响结论不被覆盖，闭环率与受影响数量分开展示；
- 补上闭环：从“给出处置建议”前进到“记录处置并复测关闭”；
- 可审计：每条处置记录带事件、资产、版本前后、处置人、时间与复测结果；
- 不造假：合成资产上的处置记录会被限制说明标注，不与真实生产修复混同。
