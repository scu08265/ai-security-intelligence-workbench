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
