# 任务书 2026-10-18：A 的收口清单

**当前基线**：`main = 2c8c7b1`；全量 **733 passed / 0 skipped**；CI 在当前 head 全绿
（`container / rollback / test`，run 39095078450，已写入 `reports/ci-validation.json`）；
页面 4 / 4 模块正常；快照与报告为 2026-10-18。

你手上还有三件事，按优先级排列。**A4 不用做**（我已经做了，别重复刷）。

---

## A1（最高优先）把处置运营分支合进 main

**分支**：`feat/a-disposition-operations-20261015` / `e03966a`，**目前未合并**。

**里面有什么**（我核对过）：

- `app/disposition_ops.py`（267 行）：`queue_snapshot()` / `run_disposition_ops()` / `due_soon()`；
- `POST /api/dispositions/run`：手工触发一次队列巡检；
- `tools/run_disposition_batch.py`：走 `/api/dispositions/pending` + `/api/dispositions/batch` 批量登记；
- `tools/verify_disposition_closure.py`：故障注入（仍命中区间时拒绝 verified；升级后单条复测关闭）；
- `tools/check_disposition_freeze_live.py`：分母冻结前后持平；
- `scripts/run_disposition_ops.ps1` + `install_windows_task.ps1`：每日任务 `AI-Security-Intelligence-Daily-Disposition`；
- 12 条新测试（`test_disposition_ops` 6 + `test_disposition_batch_tool` 6）；
- `docs/A_DISPOSITION_OPERATIONS_20261015.md` 与 `artifacts/a_eval/disposition-operations-20261015/`。

**为什么要合**：现在网页只有"待处置队列 + 批量登记"，没有队列巡检、到期提醒和可调度的运行记录。
你这块补的正好是"处置流程工程化"那一半，不合进来等于白做。

**要做的**：

1. `git fetch origin && git rebase origin/main`。你的分支基线是 `5cdd92f`（已含批量入口），
   与当前 main 的冲突预计只有 `app/api.py` 的 import 段（`disposition_ops,` 那一行）——
   解决时保留两边：既有 `disposition,` 也有 `disposition_ops,`。
2. 合完立刻跑 `python -m pytest -q`，期望 **745 passed / 0 skipped**（733 + 你 12 条；
   如果你合并时删改过测试，按实际数字写）。
3. 确认 `scripts/install_windows_task.ps1` 只是**新增**每日任务，不动现有的
   `AI-Security-Intelligence-Hourly-Collection`。
4. 起服务后手工打一次 `POST /api/dispositions/run`，确认产生一条 `kind=disposition` 的运行记录，
   且 `policy.auto_close=false`。
5. 更新 `docs/A_DISPOSITION_OPERATIONS_20261015.md`：把基线 commit、测试数、运行 id 改成合并后的实测值。

**验收**：main 上全绿；`/api/dispositions/run` 可用；任务计划里每小时采集与每日处置两个任务并存；
文档数字与实测一致。

**红线**：不要打开自动关闭。`verified` 必须逐条走系统复测，`accepted` 必须是人做的决策。
这批 44 条 `accepted` 是我按队长决定登记的，**不要改它们的状态，也不要改口径**。

---

## A2 把闭环率往上推——只剩这一条诚实路径

**现状（2026-10-18 实测）**：

| 项 | 值 |
| --- | --- |
| 高优先级 | 55 |
| 已关闭 | 47（复测 3 + 接受风险 44） |
| 闭环率 | **85.45%** |
| 待处置 | **6 条，全部在 `vllm` 资产（version 0.10.0）** |

6 条正是：`CVE-2026-100647`、`100650`、`100651`、`100654`、`103241`、`105759`。

**你在副本上已经验证过这条路**：A3 里把 `vllm 0.10.0 → 0.30.0` 后 3 条单条复测关闭
（`assessment_status_before=affected` → `after=not_affected`，写入 `closed_at`）。
但那是**你的副本**，演示机上的资产仍是 0.10.0，这 6 条仍 open。

**要做的**：

1. 在这台演示机上确认 `vllm` 的真实可用版本：6 条 CVE 的受影响区间分别是什么、
   升到哪个版本能同时跳出全部 6 个区间（你在副本里用的是 0.30.0，需在本机逐条核对）。
2. 如果确实可升级：更新资产版本 → 对 6 条逐条请求 `verified`（系统复测）→ 把每条的
   `verification.passed` / `assessment_status_before|after` 记下来。
3. 如果升不了（版本不存在、或仍是演示资产）：**保持 open**，写一份半页说明
   "为什么现在不能升级"，附上每条 CVE 的区间与本机版本。

**验收**：给出处置前后六个读数对照（total / closed / verified / accepted / open / unopened）；
每条关闭都带复测证据。**不接受**"只改状态不跑复测"。

**红线**：

- 不许批量 `verified`（接口本身也拒绝）；
- 不许直接改数据库改状态；
- 不许把 `accepted` 说成"已修复"——页面卡片是分列的（已复测关闭 / 已关闭合计 / 已接受风险）。

---

## A3 连续运行 ETA 按新口径重算

**口径变化**（10-18 已修）：`monitoring_7d` 的窗口数字以前取的是全历史账本，
"7 天窗口"里报过 13 天。现在是真正的 7 天窗口，并新增了 `continuous_executed_days`。

**当前读数**：

| 项 | 值 |
| --- | --- |
| 7 天窗口内有定时运行的日期 | 6 天 |
| 连续有定时运行的天数 | 5 天 |
| 累计定时运行日期 | 13 天 |
| `target_met` | false |
| 日界 | UTC 00:00（北京 08:00） |

**要做的**：按当前账本重算"哪天能连续满 7 天"，写进
`docs/A_CONTINUOUS_RUN_STATUS_20261015.md`（或新建 `_20261018`），并注明日界是 UTC。
报告里现在写的 ETA 是 2026-10-20，那是旧口径算的，需要复核或替换。

**验收**：连续天数、缺口日期、预计达成日期三者能互相对上；文档与页面读数一致。

---

## A4 不用做（已完成，避免重复）

- **CI 证据**：已刷新到 `1c5bf43`（run 39095078450，三 job success），
  `reports/ci-validation.json` 已提交。你不要再刷，除非你自己又推了代码。
- **报告与快照**：10-18 已重生成（含 85.45%）。**只有当你改了资产/处置数据**（即做了 A2 的升级），
  才需要重跑一次：

  ```powershell
  python tools/refresh_metrics_snapshot.py --write --tests "745 passed / 0 skipped"
  python tools/build_technical_report.py
  ```

  否则不要动，避免两边数字对不上。

---

## 时间与提交

| 步骤 | 预估 | 提交方式 |
| --- | --- | --- |
| A1 rebase + 冲突 + 测试 | 60–90 分钟 | 推分支 → PR → 队长合 |
| A2 版本核对（+ 可能的升级与复测） | 30–60 分钟 | 数据改动 + 证据文档 |
| A3 ETA 重算 | 15–20 分钟 | 文档 |
| A4 | — | 不用做 |

合 PR 前请贴三行：全量测试汇总、`/api/dispositions/run` 的运行 id、任务计划里两个任务的状态。
