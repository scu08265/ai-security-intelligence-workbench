# A: disposition live closure evidence (20261008 database / 20261009 run)

## What changed

- 在**真实生产库** `data/intel.sqlite` 的独立副本上重跑处置闭环状态机，产物落在
  `artifacts/a_eval/disposition-live-closure-20261008/`。
- 新增 `source-db-state.json`，记录生产库生成前的行数与 SHA256（生产库本身未被改写）。
- 重建项目 `.venv`：原环境指向已不存在的 Codex 运行时 Python，无法运行任何测试。

## Verification

- 缺指派人被拒（HTTP 400，无状态迁移）。
- 仍受影响的版本从 `verified` 降级为 `fixed`，保留失败的复测审计记录。
- 安全版本复测通过并写入 `closed_at`，原始 `assessments.status=affected` 不被覆盖。
- `closure_rate` 0.0 → **0.75**；`verified_rate` 0.0 → **0.75**（仅用 API 指标）。
- `/api/dispositions/metrics` 与 `/api/competition/scorecard.disposition` 字段差异 **0**。
- 全量测试：**590 passed, 59 skipped, 0 failed**（2026-10-10 修复 ACL 后普通权限裸跑 44.31s）。
- 生成前后 `data/intel.sqlite` SHA256 一致：`b4f99eae5c9200e62e439a3d83ea7e1b71909d7e29a810ce5ef1b3a8092637d8`。

## Evidence

- `artifacts/a_eval/disposition-live-closure-20261008/evidence.json`
- `artifacts/a_eval/disposition-live-closure-20261008/before-after.json`
- `artifacts/a_eval/disposition-live-closure-20261008/page-consistency.json`
- `artifacts/a_eval/disposition-live-closure-20261008/state-machine-rules.csv`
- `artifacts/a_eval/disposition-live-closure-20261008/closure-timeline.csv`
- `artifacts/a_eval/disposition-live-closure-20261008/source-db-state.json`
- `artifacts/a_eval/disposition-live-closure-20261008/pytest-result.txt`
- `artifacts/a_eval/disposition-live-closure-20261008/README.md`
- `artifacts/a_eval/disposition-live-closure-20261008/denominator-freeze.json`
- `artifacts/a_eval/disposition-live-closure-20261008/state-machine-recheck.json`
- `artifacts/a_eval/disposition-live-closure-20261008/db-backup.json`
- `artifacts/a_eval/disposition-live-closure-20261008/cohort-search.json`
- `docs/A_DISPOSITION_LIVE_CLOSURE.md`

## Recheck added 2026-10-10

- 分母冻结独立复算：重跑研判后 4 条队列条目的实时结论全部翻转为 `not_affected`，
  队列与闭环率仍为 4 / 3 / 0.75；未启用冻结口径时分母归零、闭环率变 `null`。
- 状态机四条规则在另一份独立副本上二次实测，4 / 4 通过。
- 备份恢复演练：复制回读后 SHA256、行数一致，`PRAGMA integrity_check` = `ok`。
- 全机 26 个 sqlite 队列扫描：没有任何库含 34 条高优先级队列，任务书的 34 / 11.76% 基线
  在本机无法复现，已写入 `cohort-search.json` 与 `docs/A_DISPOSITION_LIVE_CLOSURE.md`。
- 两条复核都经 `fastapi.testclient` 走真实路由（`invocation_mode=http_testclient`）。
- 修复失效 `.venv`（原指向已被清空的 Python 3.13）：用 `uv` 取独立 CPython 3.12.15 重建，
  再跑 `pytest tests -q` 得 **590 passed, 59 skipped**，原始输出见
  `pytest-result-recheck-20261010.txt`。
- 页面截图用真实浏览器补齐：`uvicorn` + Playwright(本机 Edge) 打开“赛题指标”，
  截取处置闭环卡片操作前（4 / 0 / 0%）与操作后（4 / 3 / 75%），见 `screenshots/`；
  卡片 / `/api/competition/scorecard` / `/api/dispositions/metrics` 三处字段差异 0
  （`page-consistency-20261010.json`）。
- 仍未完成：Docker 验收（守护进程未运行）。详见 `docs/A_DISPOSITION_LIVE_CLOSURE.md` 第 8 节。

## Limitations

- 生产库生成前 `assets=0`、`assessments=0`、`assessment_dispositions=0`（仅 `events=210`、
  `runs=272`、`rag_chunks=849`）。因此本轮 “live” 指的是**在真实生产库副本上、用当前 `main`
  代码走完整 API 闭环**，不代表生产环境已存在真实高危闭环。
- 选中的 4 条高优先级 `affected` 全部来自合成 `asset-cdx-*` 资产；7 个真实运行时依赖资产已导入
  并参与研判，但该事件/组件交集没有产生高优先级条目。
- `D:\ICT\intel-data-b-poc-20261002` 不在本机，无法复现其中 27 条基线。
- commit `b3e09b3` 提到的冻结口径场景（闭环率保持 11.76% 而非跌到 3.23%）在本机无可复现的库：
  现存 sqlite 中没有任何一个含 34 条高优先级队列。
- `verified` 只表示系统按当前资产版本重新研判通过，不代表生产环境已实际执行升级。
- `artifacts/backups/intel-20261008-211841.sqlite` 在本机不存在，已补做
  `artifacts/backups/intel-20261009-213026.sqlite` 后才执行。

## Environment notes

- `.venv` 原 `pyvenv.cfg` 指向 `C:\Users\17705\.cache\codex-runtimes\codex-primary-runtime\
  dependencies\python\python.exe`（已删除），本轮用系统 Python 3.13.5 重建。
- `%TEMP%\pytest-of-17705`、项目 `.pytest_cache/`、`work\pytest-*` 曾带失效 ACL，仅授权给同机
  已消失的账号 `S-1-5-21-...-1007`（当前账号为 `-1001`），`pytest` 直接跑会 `PermissionError
  [WinError 5]`。生成证据时以 `--basetemp` 指向可写目录绕过；**2026-10-10 已修复**（管理员权限
  `takeown` + 删除这些目录），普通权限裸跑 `pytest tests -q` 现通过 `590 passed, 59 skipped`。
