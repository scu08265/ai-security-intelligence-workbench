# A 项处置闭环 live 证据（2026-10-08 生产库基线）

本目录由 `tools/run_disposition_evidence.py` 在**生产库的独立副本**上通过正式 API 流程生成。
运行时间：2026-10-09 21:30 (+08:00)。代码版本：`main` @ `addeba7`，`VERSION` = `0.2.4`。

## 生成方式

```powershell
.\.venv\Scripts\python.exe tools\run_disposition_evidence.py `
  --base-db data\intel.sqlite `
  --output-dir artifacts\a_eval\disposition-live-closure-20261008
```

- 基线库：`data/intel.sqlite`，5,496,832 B，mtime `2026-10-08 18:04:16`，
  SHA256 `b4f99eae5c9200e62e439a3d83ea7e1b71909d7e29a810ce5ef1b3a8092637d8`
- 操作前备份：`artifacts/backups/intel-20261009-213026.sqlite`（本轮补做，见下方“环境问题”）
- 隔离方式：生成器只把基线库复制到本目录 `data/intel.sqlite`，再用 FastAPI `TestClient`
  走真实 API；**生产库不被改写**，全程不访问外网。

## 生产库生成前的原始状态

见 `source-db-state.json`（按生产库原文件记录，不做任何加工）：

| 表 | 行数 |
| --- | --- |
| events | 210 |
| assets | 0 |
| assessments | 0 |
| assessment_dispositions | 0 |
| runs | 272 |
| rag_chunks | 849 |

即：本轮开始时生产库里**只有采集数据，没有任何资产、研判或处置记录**。

## 结果

- 高优先级 `affected` 基线：4（全部来自合成 `asset-cdx-*` 资产）
- 复测关闭：3；失败复测并保持 `fixed`：1
- `closure_rate`：0.0 → **0.75**；`verified_rate`：0.0 → **0.75**
- 状态机规则：**4 / 4 通过**（缺指派人被拒、仍受影响版本被降级、安全版本验证关闭、原始研判状态不被覆盖）
- `/api/dispositions/metrics` 与 `/api/competition/scorecard.disposition`：**字段差异 0**
- 本次研判共 71 条 findings，其中高优先级 4 条

## 文件

| 文件 | 内容 |
| --- | --- |
| `evidence.json` | 完整请求 / 响应 / 规则结果 / 指标时间线 |
| `before-after.json` | 处置前后对比、合成/真实边界、accepted 对照组 |
| `page-consistency.json` | metrics 与 scorecard 的 8 个字段逐项核对 |
| `state-machine-rules.csv` | 4 条状态机规则逐项实测 |
| `closure-timeline.csv` | 闭环率从 0.0 到 0.75 的过程 |
| `source-db-state.json` | 生产库生成前的行数与 SHA256 |
| `pytest-result.txt` | 全量测试结果 |
| `denominator-freeze.json` | 重算研判前后的队列对比：4 条条目实时结论翻转，队列与闭环率不变 |
| `state-machine-recheck.json` | 在另一份独立副本上二次实测的 4 条状态机规则 |
| `db-backup.json` | 生产库/备份哈希、行数，以及备份恢复演练结果 |
| `cohort-search.json` | 全机 26 个 sqlite 的队列规模扫描（用于回答“34 条基线在哪”） |
| `pytest-result-recheck-20261010.txt` | 修复 `.venv` 后重跑全量测试的原始输出 |
| `page-consistency-20261010.json` | 真实页面渲染 / 计分卡 / 指标三处字段对照（操作前 + 操作后） |
| `screenshots/disposition-card-*.png` | 处置闭环卡片的真实浏览器截图（操作前 0% / 操作后 75%） |
| `screenshots/scorecard-panel-*.png` | 赛题指标整页截图 |

## 2026-10-10 复核补充

本轮新增三份证据，全部由 `tools/` 下的脚本重新计算，未修改任何已交付文件：

1. **分母冻结**（`denominator-freeze.json`）：把本目录的证据库复制到 scratch 目录后重跑
   `POST /api/assessments/run`，4 条队列条目的实时研判全部翻转为 `not_affected`，
   但 `high_priority_total` 仍为 4、`high_priority_closed` 仍为 3、`closure_rate` 仍为 0.75。
   对照推导显示：若分母跟随实时研判，分母会变成 0，闭环率会变成 `null`。
2. **状态机二次实测**（`state-machine-recheck.json`）：在另一份独立副本上重新跑四条规则，
   4 / 4 通过，失败场景留有 `verification.passed=false` 的审计记录。
3. **备份回滚**（`db-backup.json`）：备份复制到 scratch 后哈希、行数一致，
   `PRAGMA integrity_check` = `ok`。

两次复核都经 `fastapi.testclient` 走真实路由，`invocation_mode` = `http_testclient`。
本轮同时修复了失效的 `.venv`（重建为 Python 3.12.15）并重跑 `pytest tests -q`：
**590 passed, 59 skipped**，原始输出见 `pytest-result-recheck-20261010.txt`。
`%TEMP%\pytest-of-17705` 的失效 ACL 仍存在，跑测试前把 `TEMP`/`TMP` 指到 `work\pytest-temp` 即可。

4. **页面截图与三方对照**（`screenshots/`、`page-consistency-20261010.json`）：
   用 `uvicorn` 起真实服务，Playwright 驱动本机 Edge 打开“赛题指标”，
   分别对“未登记处置”的基线库与本轮证据库截图。
   卡片显示 4 / 0 / 0% 与 4 / 3 / 75%，与页面内 `fetch` 到的两个 API 逐字段一致，差异 0。

同时确认：任务书中的 `total=34 / closed=4 / 11.76%` 在本机不存在对应数据库
（`cohort-search.json` 扫描 26 个库，最大队列为 20 条）。

## 测试

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
```

结果：**590 passed, 59 skipped, 0 failed**（44.31s，2026-10-10 普通权限重跑）。

> 生成证据的当天（2026-10-09）环境带失效 ACL，必须加 `--basetemp=<可写目录> -p no:cacheprovider`
> 才能跑；该问题已于 2026-10-10 修复（见下方“环境问题”），故此处记录修复后的裸命令结果，
> 通过/跳过数量与当天完全一致。

## 声明与限制

1. 选中的高优先级条目**全部是合成 `asset-cdx-*` 资产**。
2. 7 个真实运行时依赖资产已导入并参与研判，但该事件/组件交集没有产生高优先级 `affected` 条目。
3. 生产库本轮开始时资产/研判/处置均为 0 行，因此“live”指的是**在真实生产库副本上、用当前
   `main` 代码走完整 API 闭环**，不代表生产环境已有真实高危闭环。
4. `D:\ICT\intel-data-b-poc-20261002` 数据副本不在本机，无法声称复现其中 27 条基线。
5. commit `b3e09b3` 提到的冻结口径场景（闭环率保持 `11.76%` 而非跌到 `3.23%`）在本机
   **无对应数据库**：现存所有 sqlite 中没有任何一个含 34 条高优先级队列，因此无法复现该数字。
6. `verified` 只表示系统按当前资产版本重新研判通过，**不代表生产环境已经实际执行升级**。
7. `accepted` 仅用于验证口径，不计入 `verified_rate`。

## 环境问题（复现时必须知道）

- 原有 `.venv` 已损坏：`pyvenv.cfg` 指向已不存在的 Codex 运行时
  `C:\Users\17705\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe`。
  本轮用系统 Python 3.13.5 重建 `.venv` 并 `pip install -r requirements.txt`，
  旧环境保留为 `.venv.broken-codex-20261009/`。
- 曾有多个路径带失效 ACL：`%TEMP%\pytest-of-17705`、项目内 `.pytest_cache/`、`work\pytest-*`
  只授权给同机失效账号 `S-1-5-21-...-1007`，而当前账号是 `-1001`，导致 `pytest` 报
  `PermissionError: [WinError 5]`（表现为 `24 skipped, 625 errors`）。生成证据时以
  `--basetemp` 指向可写目录绕过。**2026-10-10 已修复**：管理员权限下对上述目录执行
  `takeown` 并删除，`%TEMP%` 与 `.pytest_cache` 重新生成后属主恢复正常，普通权限裸跑
  `pytest tests -q` 现通过 `590 passed, 59 skipped`。
  注意 `icacls ... /grant "$env:USERNAME:(OI)(CI)F"` 这种写法会被 PowerShell 误解析为变量名
  （报 `无效参数"(OI)(CI)F"`），需要写成 `${env:USERNAME}:(OI)(CI)F`。
- `artifacts/backups/intel-20261008-211841.sqlite` 在 `D:\新建文件夹\2026-09-26\ba` 下
  并不存在（`artifacts/backups/` 只有 2026-09-27 ~ 10-01 的备份），故本轮先补做了
  `intel-20261009-213026.sqlite` 才执行。
