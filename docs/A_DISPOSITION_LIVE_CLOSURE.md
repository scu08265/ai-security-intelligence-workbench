# A 项处置闭环生产库落地证据（2026-10-08 基线 / 2026-10-10 复核）

## 1. 结论先行

处置闭环的代码与口径已经在**真实生产库的副本**上跑通：高优先级队列 4 条，复测关闭 3 条，
闭环率 0.75，`/api/dispositions/metrics`、`/api/competition/scorecard.disposition` 与页面绑定字段
三处零差异。分母冻结（commit `b3e09b3`）经独立复测确认生效：重算研判后 4 条队列条目的实时
研判全部从 `affected` 翻转为 `not_affected`，但队列规模与闭环率保持不变（4 / 3 / 0.75），
若不使用冻结口径，同一批数据的分母会归零、闭环率会变成 `null`。

同时必须说明：任务书给出的“生产库现状 total=34 / closed=4 / 11.76%”在本机**无法复现**，
本机不存在任何含 34 条高优先级队列的数据库（见 `cohort-search.json`，26 个库逐个扫描）。
因此本文件的数字全部来自可复现的 4 条基线，而不是任务书中的 34 条。

## 2. 现状独立复核

不采信任务书表格，直接从数据库、指标 API 与页面绑定三处分别核对。

| 项 | 任务书声称 | 本机实测 | 说明 |
| --- | --- | --- | --- |
| 高优先级待处置 | 34 | **4** | 生产库副本 `data/intel.sqlite` 的 `affected` + `high/critical` 行数 |
| 已关闭 | 4 | **3** | `verified` 计数；另有 1 条 `fixed`（复测失败降级） |
| 闭环率 | 11.76% | **0.75** | `closure_rate = high_priority_closed / high_priority_total` |
| 状态分布 | open=28, in_progress=1, fixed=1, verified=3, accepted=1 | fixed=1, verified=3 | 4 条队列条目 |
| 操作前备份 | `artifacts/backups/intel-20261008-211841.sqlite` | **不存在** | 实际使用的是 `intel-20261009-213026.sqlite` |

生产库本身的现状：`events=210`、`assets=0`、`assessments=0`、`assessment_dispositions=0`、`runs=272`。
也就是说，生产页面显示 0% 的直接原因是**生产库里没有资产与研判记录**，不是闭环率被算错。

任务书列出的处置动作里，`CVE-2026-73555`、`CVE-2026-71486` 与资产
`asset-cdx-1edc4e88dbcd6acebb9a` 在本机所有数据库中均无记录，进一步说明那批操作没有在本机落库。

## 3. 分母冻结验证

复现方式：把交付的证据库复制到 `work/disposition-freeze-recheck/freeze/`，
经 FastAPI `TestClient` 真实调用 `POST /api/assessments/run`，再读取指标。
两条 JSON 的 `invocation_mode` 都是 `http_testclient`，走的是真实路由与请求模型。

| 指标 | 重算前 | 重算后 |
| --- | --- | --- |
| `high_priority_total` | 4 | **4** |
| `high_priority_closed` | 3 | **3** |
| `closure_rate` | 0.75 | **0.75** |
| `verified_rate` | 0.75 | **0.75** |

- 重算后实时研判翻转为 `not_affected` 的条目共 24 条，其中 **4 条**是闭环队列条目，
  全部因为 `opened_at` 已写入而保留在分母内（`denominator-freeze.json` 的 `cohort_flips`）。
- 对照推导：如果分母跟随实时研判，同一批数据的 `high_priority_total` 为 0，
  `closure_rate` 为 `null`。冻结口径不是装饰性代码。
- `metrics` 与 `scorecard.disposition` 在重算后逐字段一致（除各自的时间戳）。

## 4. 状态机四条规则（独立实测）

在**另一份**独立副本上重新走一遍，避免与已交付证据互相覆盖。

| 规则 | 实测结果 | 证据 |
| --- | --- | --- |
| 未填处置人不能进入流转 | 拒绝，HTTP 400，无状态迁移 | `detail="进入处置流转必须填写处置人（assignee）"` |
| 仍受影响版本标记 `verified` | 降级为 `fixed`，`closed_at=null`，保留失败复测记录 | `verification.passed=false`，`reasons_after=["资产版本 0.10.0 命中受影响区间"]` |
| 升级到安全版本后标记 `verified` | 通过并写入 `closed_at` | `0.10.0 → 0.11.1`（另一条 `1.20.0 → 1.21.0`），`applied_status=verified` |
| 关闭后原始研判不被覆盖 | `assessments.status` 仍为 `affected` | 处置状态 `verified`，研判仍是 `affected` |

## 5. 页面、API、报告口径一致

- 两个 API：`/api/dispositions/metrics` 与 `/api/competition/scorecard` 的 `disposition` 字段，
  8 个字段逐项核对，差异 0（`page-consistency.json`）。
- 页面绑定：`app/static/app.js` 的“处置闭环”卡片读取的就是 `/api/competition/scorecard` 的
  `disposition` 字段，没有二次换算，因此页面值与 API 同源。
- 页面截图（真实浏览器渲染，非手绘）：`screenshots/disposition-card-before.png` 与
  `screenshots/disposition-card-after.png`，另有整页 `scorecard-panel-*.png`。
  做法是用 `uvicorn` 起真实服务，再用 Playwright 驱动本机 Edge 打开“赛题指标”页，
  点击后截取处置闭环卡片（脚本 `tools/capture_disposition_screenshots.py`）。
- 页面三处对照（`page-consistency-20261010.json`）：卡片渲染出来的
  高优先级总数 / 已复测关闭 / 闭环率，与截图当时从页面内 `fetch` 拿到的
  `/api/competition/scorecard` 和 `/api/dispositions/metrics` 逐字段一致，差异 0。

| 场景 | 卡片“高优先级总数” | 卡片“已复测关闭” | 卡片“闭环率” | 一致性 |
| --- | --- | --- | --- | --- |
| 操作前（未登记处置） | 4 | 0 | 0% | 一致 |
| 操作后（本轮证据库） | 4 | 3 | 75% | 一致 |

## 6. 备份与回滚

- 生产库：`data/intel.sqlite`，SHA256 `b4f99eae5c9200e62e439a3d83ea7e1b71909d7e29a810ce5ef1b3a8092637d8`。
- 生产备份：`artifacts/backups/intel-20261009-213026.sqlite`，哈希与生产库一致（备份在操作前完成）。
- 恢复演练：把备份复制到 `work/disposition-restore-drill/intel-restored.sqlite`，
  `sha256` 与行数完全一致，`PRAGMA integrity_check` 返回 `ok`（`db-backup.json`）。
- 回滚是文件级替换：停服务 → 保留当前库 → 用备份覆盖 `data/intel.sqlite` → 重启 → 校验
  `/api/health`。具体命令见 `db-backup.json` 的 `rollback_commands`。

## 7. 口径边界（必须随证据一起引用）

1. 本轮 4 条高优先级条目**全部来自合成资产**（`asset-cdx-*` 与本机演示资产）。
   本机没有任何真实生产资产，因此 0.75 是**流程落地率**，不是生产环境的真实修复率。
2. `verified` 表示系统按当前资产事实复测通过，**不代表生产环境真的执行过升级**。
3. `accepted` 只表示处置决策，不计入 `verified_rate`，也不改变原始受影响结论。
4. 原始 `assessments.status` 永远不会被处置记录覆盖；处置记录只是叠加在研判之上的第二层事实。
5. 与上一轮 `artifacts/a_eval/disposition-closure-20261004/` 的区别：上一轮是独立处置副本上的
   状态机验证，本轮是在**生产库当前状态**的副本上重跑，并补上分母冻结复核、备份恢复演练、
   队列全库扫描与状态机二次实测；两轮证据都保留，没有任何删除或覆盖。
6. 任务书中的 34 / 4 / 11.76% 基线在本机不存在，本文件不使用该数字作为自己的结论。

## 8. 未完成项与环境阻塞

| 项 | 状态 | 说明 |
| --- | --- | --- |
| 34 / 4 / 11.76% 基线复现 | **无法完成** | 本机 26 个 sqlite 中没有一个含 34 条高优先级队列 |
| `pytest -q` 全量测试 | **通过** | `590 passed, 59 skipped`（Python 3.12.15，见 `pytest-result-recheck-20261010.txt`） |
| 分母冻结 + 状态机复核走真实 HTTP | **通过** | 两份 JSON 的 `invocation_mode` 均为 `http_testclient`，即经 FastAPI 路由 |
| 页面截图（操作前/后） | **通过** | 真实渲染截图 4 张，页面/计分卡/指标三处字段差异 0 |
| Docker 重建与验收 | **未执行** | Docker 守护进程未运行（`npipe:////./pipe/docker_engine` 不存在） |

### 运行时修复

复核开始时本机只剩 Python 3.9，`.venv` 的 `pyvenv.cfg` 指向已被清空的
`C:\Users\17705\AppData\Local\Programs\Python\Python313`，FastAPI 完全不可用。本轮修复方式：

1. 用 `uv` 拉取独立 CPython 3.12.15 到 `D:\新建文件夹\2026-09-26\ba\.runtimes\uv-python`（仓库外）。
2. 把失效的 `.venv` 改名为 `.venv.broken-python313-20261010` 保留，重建 `.venv` 指向新的 3.12.15，
   再装 `requirements.txt`。修复后 `.\.venv\Scripts\python.exe -m pytest tests -q` 可用。
3. `%TEMP%\pytest-of-17705` 仍带失效 ACL（表现为 `24 skipped, 625 errors`）。本轮把
   `TEMP`/`TMP` 指到 `work\pytest-temp` 绕过，未修改该目录的权限。
4. `tools/compat/click.py` 只是 Python 3.9 时期的兼容垫片，3.12 环境下用不到。

`state-machine-recheck.json` 与 `denominator-freeze.json` 都会记录被复核数据库的 SHA256。
分母冻结复核使用的是本目录已交付证据库的副本；状态机二次实测需要一份“尚未登记处置”的基线，
本机对应 `work/disposition-trial-cdx/intel.sqlite`（`work/` 不入库，因此只记录哈希与行数）。
评审者若要复跑，可用 `--recheck-db` 指向任何同等基线。

## 9. 技术报告可用段落

处置闭环在真实生产库的隔离副本上完成了端到端验证：4 条高优先级条目中 3 条经系统复测关闭、
1 条因复测未通过被降级为 `fixed` 并保留失败审计，闭环率由 0.0 升至 0.75，指标接口、
计分卡接口与页面绑定三处零差异。分母冻结修复经独立复算确认有效：重算研判后全部队列条目的
实时结论翻转为不受影响，队列规模与闭环率仍保持 4 / 3 / 0.75，而未启用冻结口径时分母会归零。
状态机的四条约束（必须填写处置人、未修复不得关闭、安全版本方可关闭、原始研判不被覆盖）全部
实测通过，备份经恢复演练校验哈希与完整性一致。需要说明的是，本轮队列全部来自合成资产，
该闭环率衡量的是流程落地程度，不代表生产环境已发生真实修复。

## 10. 复现命令

```powershell
cd "D:\新建文件夹\2026-09-26\ba\ai-security-intelligence-workbench"

# 分母冻结复核 + 状态机二次实测（写入 denominator-freeze.json / state-machine-recheck.json）
.\.venv\Scripts\python.exe tools\run_disposition_freeze_recheck.py

# 队列全库扫描（写入 cohort-search.json）
.\.venv\Scripts\python.exe tools\scan_disposition_cohorts.py

# 备份身份与恢复演练（写入 db-backup.json）
.\.venv\Scripts\python.exe tools\verify_disposition_backup.py

# 页面截图（操作前 / 操作后各一张卡片 + 整页）
.\.venv\Scripts\python.exe tools\capture_disposition_screenshots.py `
  --data-dir work\shot-before --label before `
  --output-dir artifacts\a_eval\disposition-live-closure-20261008\screenshots
.\.venv\Scripts\python.exe tools\capture_disposition_screenshots.py `
  --data-dir work\shot-after  --label after `
  --output-dir artifacts\a_eval\disposition-live-closure-20261008\screenshots

# 全量测试
$env:TEMP="$PWD\work\pytest-temp"; $env:TMP=$env:TEMP
.\.venv\Scripts\python.exe -m pytest tests -q
```

三个脚本在 `fastapi` 可用时自动改用 `fastapi.testclient` 走真实 HTTP（产物里
`invocation_mode=http_testclient`），否则退回直接调用路由背后的处理函数
（`invocation_mode=direct_handler`），并在 JSON 里记录降级原因。
