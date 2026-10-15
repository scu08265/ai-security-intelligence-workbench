# 处置闭环工程化：队列、编排与复测真实性（A，2026-10-15）

对应任务书 `docs/TASK_BRIEF_20261015.md` 的一、二、三、四节里分给 A 的部分。
分支 `feat/a-disposition-operations-20261015`，证据目录
`artifacts/a_eval/disposition-operations-20261015/`。

## 0. 先说运行环境（不然后面的数字没法读）

本轮全部读数来自**成员 A 的机器**本仓库 `data/intel.sqlite`：

| 项 | 本机读数 | 演示机读数（任务书第一节） |
| --- | ---: | ---: |
| 高优先级队列 | **5**（critical 0 + high 5） | 53（critical 37 + high 16） |
| 从未登记处置 | **5** → 执行后 0 | 47 |
| 资产 | 3 条，全部 `is_demo=true` | 8 条，全部 `is_demo=true` |

本机队列小是因为这台机器的研判规模小，不是因为流程不同。复跑命令一样，
在演示机上执行会得到 47 条那一版结果。**两个环境的数字不得混引。**

## 1. A1：用新入口把队列真实推进一批

工具：`tools/run_disposition_batch.py`，全程走正式 HTTP 路由
（`GET /api/dispositions/pending` → `GET /api/events/{id}` / `GET /api/assets`
→ `POST /api/dispositions/batch`），不直接写库。

### 1.1 登记前后的五个数

取自 `/api/dispositions/metrics`，原始响应在 `metrics-before.json` / `metrics-after.json`。

| 指标 | 登记前 | 登记后 |
| --- | ---: | ---: |
| `high_priority_total` | 5 | 5 |
| `high_priority_registered` | **0** | **5** |
| `high_priority_unopened` | **5** | **0** |
| `closure_rate` | 0.0 | 0.0 |
| `registered_closure_rate` | `null` | 0.0 |

闭环率登记前后都是 0：**登记不等于关闭**。这一步只把"没人接手"变成"有人在办"，
关闭留给第 3 节的系统复测。

### 1.2 每条的动作与依据

5 条判定结果（`classification.json`）：

| 事件 | 资产版本 | 受影响区间 | 分类 | 动作 |
| --- | --- | --- | --- | --- |
| CVE-2026-100651 | vllm 0.10.0 | `< 0.29.0` | synthetic_actionable | 批量登记 `in_progress`，目标 0.29.0 |
| CVE-2026-100650 | vllm 0.10.0 | `<= 0.29.0`（+ `< 0.30.0`） | synthetic_actionable | 批量登记 `in_progress`，目标 0.30.0 |
| CVE-2026-100647 | vllm 0.10.0 | `< 0.29.0` | synthetic_actionable | 批量登记 `in_progress`，目标 0.29.0 |
| CVE-2026-100654 | vllm 0.10.0 | `< 0.29.0` | synthetic_actionable | 批量登记 `in_progress`，目标 0.29.0 |
| CVE-2026-103241 | vllm 0.10.0 | `<= 0.26.0`（+ `< 0.27.0`） | synthetic_actionable | 批量登记 `in_progress`，目标 0.27.0 |

登记时逐条带上 **处置人 `a-ops`、处置前版本 `0.10.0`、处置说明**；批量入口的返回
逐条给出 `applied_status`，`applied=5 / requested=5`，没有一条被静默丢弃。

### 1.3 没登记的是哪些、为什么

**本机这一轮：没有未登记条目**（`unregistered: []`）。

但"没有未登记"是这台机器的结果，不是通用结论。工具里固定了三条**不登记**的规则，
任何一条命中都会把条目写进 `unregistered` 并说明原因：

1. 事件没有可解析的受影响区间 → 判定不了动作，不登记；
2. 资产不是合成演示资产（`is_demo=false`）→ 本机没有该资产的变更授权，不代做升级；
3. 算出的安全版本不高于当前版本，或区间无法解析 → 不登记。

这三条对应任务书里"判定不了或资产本身不真实 → 不登记，写清原因"。
**没有任何一条会被登记成"已复测关闭"**：批量入口在设计上就不接受 `verified`
（`POST /api/dispositions/batch` 只用于 `in_progress` / `fixed` / `accepted`）。

## 2. A2：把处置流程编排成可调度的运行

补的是"系统里没有任何自动处置流程"这条根因。

### 2.1 一次运行做了什么

`app/disposition_ops.py` 的 `run_disposition_ops()` 按四个阶段走一遍队列，
每个阶段都留痕：

| 阶段 | 做什么 | 本轮读数 |
| --- | --- | --- |
| `queue` | 队列构成快照：待处置 / 已登记 / 各状态计数 | 待处置 0，队列 5，已登记 5，verified 3 / in_progress 2 |
| `assign` | 指派检查 + 到期未处置提醒（默认 24 小时） | 未指派 0，逾期 0 |
| `recheck` | 复测到期扫描（`fixed` 待复测超过 24 小时） | 待复测 0 |
| `close_or_accept` | 已关闭 / 已接受风险的只读汇总 | 已关闭 3，接受风险 0 |

命中逾期或待复测会各发一条 warning 告警（`disposition_overdue` /
`disposition_recheck_due`），severity 与告警口径沿用既有规则。

### 2.2 运行记录与调度留痕

运行记录（`kind="disposition"`，可从 `/api/runs` 读回）：

```json
{
  "id": "run-525456887f4b",
  "kind": "disposition",
  "status": "completed",
  "summary": "处置队列巡检：待处置 0，处置中 2，待复测 0，逾期 0 条",
  "detail": {
    "scheduler": {
      "task_id": "daily-disposition-queue",
      "planned_at": "2026-10-15T14:32:02Z",
      "actual_at": "2026-10-15T14:32:02Z",
      "trigger_source": "windows_task_scheduler_or_cron"
    },
    "scheduler_trace": ["queue", "assign", "recheck", "close_or_accept"],
    "queue": { "pending_total": 0, "queue_total": 5, "closure_rate": 0.6 }
  }
}
```

`scheduler_trace` 与 `collect` 运行同形：每个阶段有 `stage` / `status` / `at` / `detail`，
所以"队列 → 指派 → 复测 → 关闭/接受风险"每一步都能在运行记录里核查，
而不是只存在于某个脚本里。

`/api/dispositions/pending` 的读数随运行一起被写进 `detail.queue.pending_total`：
本轮执行前是 5，执行后是 0，运行记录里两个值都能查到。

### 2.3 接进调度器

- CLI：`tools/run_disposition_ops.py`（`--trigger scheduled|manual`）
- 计划任务外壳：`scripts/run_disposition_ops.ps1`
- 安装：`scripts/install_windows_task.ps1` 现在会额外注册
  **`AI-Security-Intelligence-Daily-Disposition`**，每天 09:00 跑一次；
  与小时级的采集任务分开，避免把提醒绑在采集节奏上。
- 手工触发（等同计划任务的一次运行）：
  `POST /api/dispositions/run`

### 2.4 明确不做自动关闭

编排**不会**替人关闭任何条目，`policy.auto_close` 恒为 `false`，并有测试钉住
（`test_the_sweep_never_closes_anything_by_itself`：巡检前后 `status_breakdown`
与 `closure_rate` 必须一模一样）。

## 3. A3：复测闭环的真实性（故障注入）

工具：`tools/verify_disposition_closure.py`，先做故障注入（把演示资产放回
`vllm 0.10.0` 并重算研判），再做两条边界验证。原始请求/响应在
`verification-evidence.json`。

### 3.1 边界一：仍命中区间 → 关闭被拒绝（反例）

| 项 | 值 |
| --- | --- |
| 事件 | `CVE-2026-100651` |
| 请求 | `PUT /api/dispositions/... ` status=`verified` |
| 实际落库状态 | **`fixed`** |
| `verification.assessment_status_before` | `affected` |
| `verification.assessment_status_after` | `affected` |
| `verification.passed` | **false** |
| `closed_at` | **null** |
| 结论 | `复测未通过：资产仍命中受影响区间，不能标记为已关闭。` |

失败的复测没有被丢掉，而是留在处置记录的 `verification` 里当审计证据。

### 3.2 边界二：升级到区间外 → 单条复测关闭（3 条）

注入内容：把合成资产 `asset-cdx-1edc4e88dbcd6acebb9a` 从 **vllm 0.10.0 升到 0.30.0**
（同时躲开 `< 0.27.0` / `< 0.29.0` / `< 0.30.0` / `<= 0.26.0` / `<= 0.29.0` 五个区间）。
**刻意不在升级后重算研判**，让每条 `verified` 自己的复测去发现变化：

| 事件 | before | after | passed | closed_at |
| --- | --- | --- | --- | --- |
| `CVE-2026-100651` | `affected` | `not_affected` | true | 写入 |
| `CVE-2026-100650` | `affected` | `not_affected` | true | 写入 |
| `CVE-2026-100647` | `affected` | `not_affected` | true | 写入 |

三条都是单条 PUT，**没有走批量入口**——批量入口不接受 `verified`，
关闭必须由系统对每条资产单独复测。

### 3.3 分母冻结复验

`tools/check_disposition_freeze_live.py` 在重算研判（`POST /api/assessments/run`）前后
各读一次指标，六个读数完全一致：

```
total=5 registered=5 unopened=0 closed=3 rate=0.6 registered_rate=0.6
```

资产已经升到区间外、研判翻成 `not_affected`，但已登记的 5 条仍在分母里
（`opened_priority` 在开单时冻结），所以闭环率不会因为"修好了"而突然变化。

### 3.4 本轮结束时的状态

队列 5 条：**3 条已复测关闭、2 条仍在处置中**。剩下的 2 条是**故意留的**：
它们的资产已经升级，随时可以走复测关闭，但保留在队列里才能说明
"这条流水线不是一次性把队列清空给你看"。

## 4. A4：CI 证据与连续运行

- `reports/ci-validation.json` 已刷新到当前 main `185b55e`，run `38739007034`，
  **test / container / rollback 三个 job 全 success**。
- 连续运行核对：`tools/check_continuous_run.py --days 7`。
  2026-10-15 当天已有计划运行记录（01:46Z 起，最近一次 06:46Z），
  缺口仍是 10-09 / 10-11 / 10-12 / 10-13 四天（机器休眠或关机期间计划任务不补触发）。
  `target_met = false`，**预计 2026-10-20 回到 true**（前提是每天至少一次计划运行）。

## 5. 口径与边界

1. **本机 5 条高优先级全部来自合成资产**（`is_demo=true`，vllm/uvicorn/fastapi 三条
   CycloneDX 演示资产），本机没有真实生产资产。
2. 因此本节所有比率都是**流程落地率**：它衡量"系统能不能把一条处置从队列推到
   复测关闭"，**不是生产环境的真实修复率**。3/5 = 60% 说的是流程走得通，
   不是"60% 的漏洞被修好了"。
3. `verified` 的含义是"系统按**当前资产事实**复测通过"，不代表生产环境真的执行过升级。
   本轮的升级动作改的是演示资产的版本字段，已在介质上标注为合成。
4. **接受风险 ≠ 风险消除**：`accepted` 只表示处置决策，原始 `assessments.status`
   不被覆盖，仍留在闭环率分母内。
5. 台账与页面的口径不可互换：`closure_rate` 的分母是全队列，
   `registered_closure_rate` 的分母只含已登记处置的条目。

## 6. 复跑

```powershell
# 需要服务在跑：.\.venv\Scripts\python.exe -m uvicorn app.api:app --port 8020
.\.venv\Scripts\python.exe tools\run_disposition_batch.py --base http://127.0.0.1:8020
.\.venv\Scripts\python.exe tools\verify_disposition_closure.py --base http://127.0.0.1:8020 --reset-to-version 0.10.0
.\.venv\Scripts\python.exe tools\check_disposition_freeze_live.py --base http://127.0.0.1:8020
.\.venv\Scripts\python.exe tools\run_disposition_ops.py --trigger scheduled
```

测试：`pytest tests/test_disposition.py tests/test_disposition_ops.py
tests/test_disposition_batch_tool.py -q`（本机全量 650 passed / 4 skipped，
4 条跳过是需要 B 任务衍生语料的那几条）。

## 7. 结论（可直接进技术报告）

处置闭环的 7.55% 不是处置能力差，而是队列没人接手：53 条里 47 条从未开单。
本轮把"接手"这件事做成了新入口——批量登记、单条复测、逐条留痕，并把
「队列 → 指派 → 复测 → 关闭 / 接受风险」编排成一条可调度的 `disposition` 运行，
每次巡检都记下队列读数与四个阶段的状态。复测不是走过场：故障注入下，
资产仍在受影响区间时关闭被拒绝并留成 `fixed` + 失败复测记录，升级到区间外后
才以 `affected → not_affected` 的复测证据关闭；重算研判前后闭环率持平，
说明分母冻结规则成立。需要说清的是，本机 5 条全部落在合成演示资产上，
所以这些比率是**流程落地率**，不是生产环境的真实修复率。
