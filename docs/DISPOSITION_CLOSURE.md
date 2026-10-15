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

`GET /api/dispositions/metrics` 与 `/api/competition/scorecard` 的 `disposition` 字段。

### 4.1 两个比率（分母不可互换）

一个比率分不清"处置失败"和"根本没人接手"，所以接口同时给两个分母：

| 字段 | 分子 | 分母 | 回答的问题 |
| --- | --- | --- | --- |
| `closure_rate` | `high_priority_closed` | `high_priority_total`（**全队列**） | 整个高优先级队列里关闭了多少 |
| `registered_closure_rate` | 已登记处置且已关闭 | `high_priority_registered`（**只含已登记处置的条目**） | 已经接手的那些处理得怎么样 |

配套计数字段：`high_priority_registered`（已登记处置）、`high_priority_unopened`（从未登记处置）。

**两个分母不可互换**：`closure_rate` 低可能是"没人接手"，`registered_closure_rate` 低才是"接手的没处理好"。
引用时必须写明用的是哪一个分母；只写"闭环率"而不说分母，等同于制造歧义。

### 4.2 分母冻结规则

处置记录会把登记那一刻的 `opened_priority` 一起存下来。资产修复后重算研判会把该条刷成
`not_affected`，但它**不会离开分母**；否则一次成功的修复会同时缩小分子和分母，
让闭环率在修好的瞬间反而塌回 0。原始 `assessments.status` 也永不被处置记录覆盖，
`affected` 事实长期保留。

### 4.3 其余字段

- `high_priority_closed`：该队列中状态为 `verified` 或 `accepted` 的数量；
- `verified_rate`：只统计系统复测通过的关闭（`verified`），与 `accepted` 分开；
- `mean_time_to_close_hours`：仅统计同时有 `opened_at` 与 `closed_at` 的记录，样本为空时为 `null`；
- `status_breakdown`：高优先级闭环队列在各状态上的分布，**各分项之和等于 `high_priority_total`**；
- 分母为 0 时比率返回 `null`，不返回 0。

### 4.4 接口 `limitations` 的原文（照抄，不要改写标点或加粗）

> 合成演示资产上的处置记录不等于生产环境的真实修复。
> 接受风险（accepted）只表示处置决策，不代表风险已消除。
> 平均关闭时长只统计已有 opened_at 与 closed_at 的记录。
> closure_rate 的分母是全队列；registered_closure_rate 的分母只含已登记处置的条目，两者不可互换。

这四条与 `GET /api/dispositions/metrics` 的 `limitations` 数组**逐字一致**，
由 `tests/test_disposition.py::test_closure_scope_is_documented_verbatim` 守护：
文档里少一句、或改写标点，测试就会失败。

**为什么单独强调"接受风险 ≠ 风险消除"**：`accepted` 会进 `high_priority_closed` 的分子，
所以它**会抬高闭环率**；但它只是"决定不修"的处置决策，风险本身仍然存在。
原始 `assessments.status=affected` 事实、以及资产的受影响版本区间都不会因此改变。

**为什么单独强调"合成资产上的处置 ≠ 生产修复"**：演示库里的资产
（`config/assets.example.json`，`synthetic=true`、条目 `is_demo=true`）没有真实补丁动作，
在其上登记的 `verified` 只证明"系统复测链路可用"，不证明任何生产系统被修好。

### 4.5 当前读数（2026-10-15，`/api/dispositions/metrics`）

| 项 | 读数 |
| --- | --- |
| 高优先级队列 | 53 条（critical 37 + high 16） |
| 已复测关闭 | 4 条 |
| 全队列闭环率 | **4 / 53 = 7.55%** |
| 已登记处置 | 6 条 |
| 从未登记处置 | **47 条** |
| 已登记处置内闭环率 | **4 / 6 = 66.67%**（`registered_closure_rate`） |

**怎么读这一组数**：7.55% 低，是因为 53 条里 **47 条从未被接手**——根因是系统此前没有自动处置编排，
不是处置能力差；同样这 6 条登记过的记录里 4 条已关闭或已接受风险，即 66.67%。
两个数一起讲，并说明分母不同。数值随采集与处置变化，快照以 `docs/METRICS_BASELINE.md` §2 为准。

> **运行环境限定（2026-10-12 补，保留备查）**：早期出现过的 `4 / 0.75` 是 **A 机器**上那份数据库
> 副本的读数（`D:\新建文件夹\2026-09-26\ba\...\data\intel.sqlite`），该库不在交付机上，
> 属于"流程落地演示"，不是交付闭环率。规则见 `docs/METRICS_BASELINE.md` 第 3 节：
> 不同数据集的数字不得混排在同一张指标表里。

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
