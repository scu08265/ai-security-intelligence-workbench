# 处置闭环往上推一步（A2，2026-10-18）

## 1. 前提与差别

任务书给的现状是演示机：55 条高优先级、47 已关、6 条 open 全在 vllm 0.10.0。
本机（成员 A 的机器）不是这个状态：

- 本机 vllm 资产**已经是 0.30.0**（10-15 那轮 A3 升上去的，之后没有再降回去）；
- 所以同样这 6 条事件，在本机的研判结果都是 `not_affected`；
- 队列里只剩 2 条仍处于处置中：`CVE-2026-100654`、`CVE-2026-103241`；
- `CVE-2026-105759` 在本机是"有事件、本轮之前没有研判"，跑了一次研判后落在
  `not_affected / low`，因此**没有进入高优先级队列**——它在演示机上 open 是因为
  演示机的资产还停在 0.10.0。

一句话：本机和演示机的差别只有资产版本这一个变量，区间与事件是同一批。

## 2. 6 条的区间核对

逐条读事件的 `affected`，并确认升到哪一版能同时跳出：

`CVE-2026-100647` 是 `< 0.29.0`；`CVE-2026-100650` 是 `<= 0.29.0` 加 `< 0.30.0`；
`CVE-2026-100651` 是 `< 0.29.0`；`CVE-2026-100654` 是 `< 0.29.0`；
`CVE-2026-103241` 是 `<= 0.26.0` 加 `< 0.27.0`；`CVE-2026-105759` 是 `< 0.30.0`。

六条取交集，**能同时跳出的最小版本是 0.30.0**（`< 0.30.0` 这条决定了不能再低）。
本机资产恰好已经是 0.30.0，所以本轮不需要再升级，也没有回写成更低的"最小安全版本"
——工具里加了保护：当前版本若已躲开所有区间就保持不变，避免把资产降级。

## 3. 前后六个读数

取自 `/api/dispositions/metrics`，原始请求在
`artifacts/a_eval/disposition-operations-20261018/verification-evidence.json`。

处置前：total 5、closed 3、registered 5、unopened 0、closure_rate 0.6、
registered_closure_rate 0.6。

处置后：total 5、closed 5、registered 5、unopened 0、closure_rate 1.0、
registered_closure_rate 1.0。

状态分布从 `in_progress 2 / verified 3` 变成 `verified 5`。

## 4. 每条的复测证据

两条都是**单条** `PUT /api/dispositions/{event}/{asset}`，没有走批量入口
（批量入口在设计上不接受 `verified`）。

`CVE-2026-100654`：`verification.passed = true`，
`assessment_status_before = not_affected`，`assessment_status_after = not_affected`，
`closed_at` 写入，`version_after = 0.30.0`。

`CVE-2026-103241`：同上，`passed = true`，`closed_at` 写入，`version_after = 0.30.0`。

**为什么 before 是 `not_affected` 而不是 `affected`**：本轮开始前资产已经是 0.30.0，
我先跑了一次正常的 `POST /api/assessments/run`（44 条研判），把库里过期的
`affected` 更新成了 `not_affected`，之后才走复测关闭。所以这两条的复测记录是
"复测再次确认 not_affected"，不是状态跃迁。

真正的 `affected → not_affected` 跃迁证据在 10-15 那轮的 3 条里
（`artifacts/a_eval/disposition-operations-20261015/verification.json`）。
如果要在本机重现完整跃迁，用：

```powershell
.\.venv\Scripts\python.exe tools\verify_disposition_closure.py --base http://127.0.0.1:8020 --reset-to-version 0.10.0 --closes 5
```

它会先把资产放回 0.10.0、重算成 `affected`，再升级并逐条复测，代价是会重写
这 5 条已有的 `closed_at`。

## 5. 分母冻结复核

关闭完成后又跑了一次 `POST /api/assessments/run`，前后六个读数完全一致
（total 5 / closed 5 / registered 5 / unopened 0 / 1.0 / 1.0），
`frozen = true`。产物：
`artifacts/a_eval/disposition-operations-20261018/denominator-freeze.json`。

## 6. 演示机上要做的

演示机资产还是 0.10.0，6 条都还开着，所以那条路径只能在那台机器上走完。
顺序是：先把 6 条登记成 `in_progress`（`tools/run_disposition_batch.py`），
再跑复测关闭（`tools/verify_disposition_closure.py --closes 6`，不要加
`--reset-to-version`，因为它会改资产版本）。命令一样，差别只在库。

## 7. 边界

- 本机 5 条全部落在合成演示资产上，1.0 是**流程落地率**，不是生产修复率；
- 资产升级改的是演示资产的版本字段，不代表生产环境执行过升级；
- 本机没有被标记为 `accepted` 的条目，也没有改动任何 `accepted` 的状态或口径；
- 没有批量 `verified`，没有直接写库。
