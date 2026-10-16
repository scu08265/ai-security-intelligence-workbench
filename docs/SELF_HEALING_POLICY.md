# 自愈与降级口径（2026-10-15 定稿）

这份文件回答 `docs/TASK_BRIEF_A_POLICY_20261015.md` 里留给 A 定的五条。每条给出
**选定选项 + 一句理由 + 影响面 + 测试覆盖**，以及四个采集状态的定义。

## 0. 一句话口径

> 降级触发条件 = **连续 3 次失败**。失败 = `failed` / `stale` / **零产出的 `partial`**；
> `ok` 与**有产出的 `partial`** 都不算失败，并且会打断 streak。

## 1. 五个决策

| 决策 | 选定 | 一句理由 | 影响面 | 测试 |
| --- | --- | --- | --- | --- |
| 1 `partial` 算不算连续失败 | **A2 分类阈值** | 撞抓取预算是采集器的设计行为，只有"跑得起来但什么都采不到"才是半坏 | `/api/system/health` 的 streak 与降级理由；无人值守来源数不再被 ghsa 拉低 | `test_a_productive_partial_never_builds_a_streak`、`test_a_zero_output_partial_counts_as_a_failure`、`test_a_productive_partial_breaks_a_failure_streak` |
| 2 `stale` 的语义 | **与 `failed` 同等计入**，并在本文第 2 节写清定义 | stale 是"连不上、但历史数据还在"，对采集本身同样是没采到 | streak 计算（行为不变，口径写实） | `test_consecutive_failures_counts_only_the_trailing_attempts` |
| 3 `partial` 是否刷新 `last_success` | **保留刷新**（语义 = 最近一次非失败运行）；页面文案改为"最近一次成功（含部分成功）" | 否则长期 partial 的来源会永远显示"从未成功"，更误导 | `/api/system/health` 的「采集与监测」行文案；`docs/screenshots/10-system-health.png` 需重截 | `tests/test_api.py` 健康面板用例 |
| 4 降级记录的 `failure_class` | **用真实的 `status` / `last_error` 计算** | 字段的意义就是"怎么坏的"，而证据一直就在手边 | 新降级记录的 `failure_class` / `last_error` / `source_status` 三个字段不再恒为 `unknown` | `test_degradation_records_the_real_failure_class` |
| 5 告警窗口要不要时间基线 | **维持条数窗口**（最近 20 条），把口径写进接口与页面 | 数据量小、实现简单；换时间窗会让"三天前的 warning"变成静默消失，反而更难解释 | `/api/system/health` 新增 `policy.alert_window`（kind/size/actionable_definition）；页面自愈说明补一句 | `tests/test_api.py::test_health_alerts_module_ignores_info_only_recoveries` |

口径不是为了让"需关注"变少：`actionable` 的判定标准一个字没动，只是把窗口含义写清楚
（**需关注 = 最近 20 条里存在 warning 及以上**）。

## 2. 四个采集状态的定义与是否计入降级

| 取值 | 定义 | 计入降级 streak？ |
| --- | --- | --- |
| `ok` | 本次采集完整跑完，拿到并保留了数据 | 否，且**打断** streak |
| `partial` | 采集器跑到预算上限就停下（例如 ghsa 的抓取预算），不静默截断；**有产出**则视为正常 | **有产出：否**（并打断 streak）；**零产出：是** |
| `failed` | 本次采集报错且没有任何历史数据兜底 | 是 |
| `stale` | 本次采集失败（多为连不上上游），但该来源**历史数据仍在**，页面继续展示旧数据 | 是 |
| `skipped` | 主动跳过（缺少凭据、来源被关闭），不是故障 | 否 |

`stale` 与 `partial` 的区别是这条口径里最容易混的：`stale` 表示**上游连不上**，
`partial` 表示**连上了但只拿回来一部分**。前者是故障，后者是设计。

`failed` 与 `stale` 的切换发生在采集写回时：`outcome.status == "failed"` 且该来源
`events_count > 0` 且有 `last_success` 时记为 `stale`（`app/agents.py`）。

## 3. 今天按新口径谁会被降级

复跑：

```powershell
.\.venv\Scripts\python.exe tools\check_degradation_policy.py
```

输出一张逐来源表（状态 / 最近一次是否有产出 / streak / 是否降级 / 动作）与
`reports/degradation-policy-check.json`。

**交付机（队长演示机）的预期**：`ghsa` 是 `partial` 且有产出（104 条事件），
所以**不在降级名单里**——这正是选 A2 要修的那条。其余来源 streak 为 0，也不降级。
改动前 ghsa 会因为别处一次 failed/stale 触发自愈而被顺带写一条新的 6 小时冷却，
改动后不会。

**本机（成员 A 的机器）的实测**：本机没有 ghsa / arxiv 的状态行（这两个源在本机没有采集
记录），全部来源 streak 为 0，因此"今天会被降级的来源"为**空**。这正是两边环境不同的
地方，引用时要带机器限定语。

## 4. 对"无人值守时段还有几个来源在产出"的影响

改动前：ghsa 被机会式降频，`apply_degradation_policy` 按 `reduce_frequency` 把它从该次
无人值守采集里移出（它没有备用源，`substituted_with=[]`）。无人值守时段的实际产出源数
会从 15 掉到 14，而且时机不可预期——取决于别处什么时候失败。

改动后：有产出的 partial 不触发降频，ghsa 留在无人值守集合里；只有真正采不到的来源
（`failed` / `stale` / 零产出 partial）才会让产出源数下降。

## 5. 与页面/接口的一致性

- `/api/system/health` 的 `policy` 段现在带 `counted_as_failure` / `not_counted_as_failure` /
  `alert_window`；自愈那行的 `detail` 写的是新口径，不再说"含 partial"。
- 「采集与监测」行的"最近一次成功（含部分成功）"对应的字段是 `source_state.last_success`，
  由 `ok` 或 `partial` 的采集戳记（`app/agents.py`）。选的是"保留刷新 + 改文案"，
  没有改字段语义。

## 6. 不做的事

- 不改 `RETRYABLE_SOURCE_STATUSES`：`partial` 仍然不进重试集合（它没有失败可重试）。
- 不改告警 `actionable` 的判定标准。
- 不为了让数字好看而放宽任何阈值。
