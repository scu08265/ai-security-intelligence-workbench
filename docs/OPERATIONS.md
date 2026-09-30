# 部署、调度、备份与回滚

## 1. 本地运行

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m uvicorn app.api:app --host 127.0.0.1 --port 8000
```

- 健康检查：`GET /api/health`
- 来源可靠性：`GET /api/system/reliability?days=7`
- 告警记录：`GET /api/system/alerts`
- 结构化日志：`GET /api/system/logs`

## 2. 每日计划采集

计划任务只运行 `sources.recommended_sources()`，即注册表中
`auto_default=true` 的来源。arXiv 和未配置 Token 的 GHSA 不进入每日自动任务。

每次运行记录：

- 任务 ID：`scheduler.task_id`
- 计划时间：`scheduler.planned_at`
- 实际开始时间：`scheduler.actual_at`
- 运行 ID、来源状态、耗时和失败原因

### Windows 任务计划：每小时

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install_windows_task.ps1 -IntervalHours 1
Start-ScheduledTask -TaskName "AI-Security-Intelligence-Hourly-Collection"
```

卸载：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\uninstall_windows_task.ps1
```

### cron

参考 [crontab.example](../scripts/crontab.example)：

```cron
0 * * * * cd /opt/ai-security-intelligence-workbench && .venv/bin/python tools/run_scheduled_collection.py --task-id hourly-recommended-sources --planned-at "$(date -Iseconds)" >> artifacts/logs/scheduled-collection.log 2>&1
```

容器环境也可以使用 `tools/run_scheduled_loop.py --interval-seconds 3600`。每个周期都会记录
`trigger=scheduled`、任务 ID、计划时间和实际时间。

## 2.1 NVD 完整分页

NVD 默认最多扫描 100 页，不再固定只取前两页。每页 200 条，成功页之间默认等待 6 秒；只有全部页完成后才推进
游标。正常窗口即使超过 400 条也不会因为页数上限标记 partial。

可选环境变量：

- `NVD_API_KEY`：启用更高 API 限额。
- `NVD_MAX_PAGES`：安全上限，默认 100。
- `NVD_PAGE_DELAY_SECONDS`：页间等待，无 Key 时默认 6 秒。

## 3. 报告生成

```powershell
.\.venv\Scripts\python.exe tools\build_reliability_report.py --days 7 --output-dir reports
```

输出：

- `reports/7-day-continuous-run-report.md`
- `reports/source-health.csv`
- `reports/source-health.json`
- `reports/latency-summary.json`
- `reports/latency-chart.svg`
- `reports/source-success-chart.svg`

首轮采集的历史事件不计入“系统开始监测后的新增事件时延”，而是在报告中列为
“历史回填排除”。`0001-01-01` 等异常日期和晚于发现时间的发布时间记为未知。

## 4. 日志与告警

- JSONL 日志：`data/logs/workbench.jsonl`
- 告警记录：`data/logs/alerts.jsonl`
- 计划任务包装日志：`artifacts/logs/scheduled-collection.log`
- 可选 Webhook：设置 `INTEL_ALERT_WEBHOOK_URL`

告警发送是尽力而为，不影响主采集流程。密钥、Token、Password 和 Authorization
字段在结构化日志中统一替换为 `[redacted]`。

## 5. 数据库备份

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\backup_database.ps1 -KeepDays 14
```

脚本使用 SQLite Online Backup API，在服务运行时创建一致性副本，默认保存在
`artifacts/backups/`。

## 6. 回滚

1. 停止当前服务。
2. 使用上一个容器镜像或 Git 工作副本。
3. 恢复备份数据库：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\restore_database.ps1 -BackupPath .\artifacts\backups\intel-YYYYMMDD-HHMMSS.sqlite
```

4. 启动服务并核对 `/api/health`、`/api/duplicate-candidates` 和最近的运行记录。

数据库文件回滚前会自动保存为 `intel.sqlite.before-restore-*`，避免再次覆盖时丢失现场。

## 7. 版本回退

- 当前发布版本记录在 `VERSION`，本文档对应 `0.2.2`。
- 发布时使用 Git 标签；回退代码时切换到上一个稳定标签。
- Docker 镜像使用 `ai-security-intelligence-workbench:<版本号>`，不要覆盖旧标签。
- 回退前先执行 `scripts/backup_database.ps1`。

```powershell
git fetch --tags
git switch --detach v0.2.2
docker build -t ai-security-intelligence-workbench:0.2.2 .
```

## 8. 连续 7 天证据

- 只有 `trigger=scheduled` 的运行计入天数。
- 人工点击采集不计入。
- 应用启动本身不计入。
- 某天有运行但状态为 `partial`，保留真实结果，不自动算作完全成功。
- 未达到 7 天时报告只能写“积累中”，不能写“稳定性已验证”。
