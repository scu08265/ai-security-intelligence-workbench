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

- `high_priority_total`：**高优先级闭环队列**的大小 —— `assessments.status=affected` 且
  `priority ∈ {critical, high}` 的结论，**加上**已登记处置、且在登记时优先级为 high/critical 的结论；
- `high_priority_closed`：该队列中状态为 `verified` 或 `accepted` 的数量；
  - 队列冻结规则：处置记录会把登记那一刻的 `opened_priority` 一起存下来。资产修复后重算研判会把
    该条刷成 `not_affected`，但它**不会离开分母**；否则一次成功的修复会同时缩小分子和分母，
    让闭环率在修好的瞬间反而塌回 0。
- `closure_rate = high_priority_closed / high_priority_total`；分母为 0 时返回 `null`，不返回 0；
- `verified_rate`：只统计系统复测通过的关闭；
- `mean_time_to_close_hours`：仅统计同时有 `opened_at` 与 `closed_at` 的记录，样本为空时为 `null`；
- `status_breakdown`：高优先级闭环队列在各状态上的分布。

当前 A 证据库：高优先级 `affected` 4 条，全部为
`asset-cdx-*` 合成资产（smolagents / open-webui）。闭环率从 `0` 增加到 `0.75`，
其中 3 条由系统复测关闭，1 条因资产版本仍在受影响区间保持 `fixed`。

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

## 7. 与 B 任务处置建议的关系

本模块只记录“实际处置”，处置动作建议仍由 `tools/asset_disposal_advisor.py` 生成。主应用通过
`GET /api/dispositions/{event_id}/{asset_id}/advice` 复用同一份建议逻辑，不复制、不重写权重：
建议是只读输入，处置记录才是系统 of record。未配置资产策略时，补丁/重启/降暴露面等破坏性动作
进入 `blocked_actions`，需要人工决策，避免系统默认替用户执行生产动作。

## 8. 2026-10-04 A 项复测证据

本节记录 `feat/a-disposition-evidence-20261004` 的独立复测结果，证据位于
`artifacts/a_eval/disposition-closure-20261004/`。

复测库由正式 API 流程创建：

1. 复制当前事件库到 A 独立证据目录；
2. 通过 `/api/assets` 导入 B 记录的 6 个合成 `asset-cdx-*` 条目；
3. 通过 `/api/assets` 导入 7 个当前运行时的真实依赖条目；
4. 通过 `/api/assets/cyclonedx/import` 导入 SBOM 资产；
5. 通过 `/api/assessments/run` 生成研判结论。

实测结果：

| 规则 | HTTP | 实际结果 |
| --- | ---: | --- |
| 未填写处置人进入 `in_progress` | 400 | 拒绝流转，记录仍为 `open` |
| 版本仍受影响时标记 `verified` | 200 | 降级为 `fixed`，`verification.passed=false` |
| 升级到安全版本后标记 `verified` | 200 | `verified`，写入 `closed_at` |
| 关闭后检查原始研判 | - | `assessments.status` 仍为 `affected` |

闭环率变化：

| 阶段 | 高优先级总数 | 已关闭 | 闭环率 | verified_rate |
| --- | ---: | ---: | ---: | ---: |
| 基线 | 4 | 0 | 0.00 | 0.00 |
| 失败复测后 | 4 | 0 | 0.00 | 0.00 |
| smolagents 复测关闭后 | 4 | 1 | 0.25 | 0.25 |
| open-webui 复测关闭后 | 4 | 3 | 0.75 | 0.75 |

页面卡片读取 `/api/competition/scorecard` 的 `disposition` 字段。A 证据库确认该字段与
`/api/dispositions/metrics` 全部核对字段一致，`field_mismatches=[]`。

## 9. 证据边界与局限

- 当前主机没有 B 记录中的 `D:\ICT\intel-data-b-poc-20261002` 数据库副本，因此不能声称
  直接复现文档曾记录的 27 条基线；A 证据库记录的是实际执行和实际得到的 4 条高优先级
  `affected` 结论。
- 选中的 4 条高优先级关系全部来自合成 `asset-cdx-*` 资产，不应当表述为企业生产环境
  的真实修复。
- 7 个真实运行时依赖资产已导入并参与研判，但它们与当前事件集的组件交集没有产生高优先级
  `affected` 条目，因此没有拿真实资产名称包装合成处置。
- `verified` 表示系统按当前资产事实重新研判通过；系统没有执行生产升级、重启、隔离或关机。
- `accepted` 只验证口径正确：它计入处置完成但不计入 `verified_rate`，不能说风险已消除。
- 当前闭环率样本量仅为 4，足以验证流程和口径，不足以作为稳定性或生产修复率结论。
