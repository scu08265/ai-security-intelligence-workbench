# A 项任务实施与验收说明

## 1. 当前状态

已完成：

- 每小时推荐来源采集入口。
- 任务 ID、计划时间、实际时间、来源结果和失败原因持久化。
- Codex 每小时自动化 `ai-a`，只使用推荐来源。
- Windows 任务计划和 Linux cron 安装脚本。
- `<=24h / <=12h / <=6h` 数量、比例、可计算样本和未知样本。
- `0001-01-01`、缺失日期和未来发布日期排除。
- 首次监测前历史回填与监测期增量时延分开统计。
- 来源成功率、失败次数、P50/P95、最近成功时间。
- arXiv、OpenAlex、OSV、MSRC、GHSA 降级策略。
- Dockerfile、Compose、健康检查、GitHub Actions。
- JSONL 结构化日志、告警记录和可选 Webhook。
- Markdown、CSV、JSON、SVG 图表和真实页面截图。

9 月 29 日发生过漏运行，连续天数从恢复日重新计算。7 天必须靠真实日历时间完成，不能补写。

## 2. 每日计划采集

Codex 自动化：

- ID：`ai-a`
- 时间：每小时一次
- 通知：仅失败时

Windows 任务计划：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install_windows_task.ps1 -IntervalHours 1
```

当前受限会话没有 Windows Task Scheduler 注册权限，因此没有在系统层注册任务；
安装脚本已完成并可在普通 PowerShell 中运行。Codex 自动化已经启用，用于继续积累
每小时证据。

## 3. 本次真实运行

- 验证运行：`run-9629821a26ca` 至 `run-2eda584fec85`
- 任务 ID：`hourly-recommended-sources`
- 状态：六个周期均为 `completed`
- 今日自动计划运行：7 条
- 推荐来源：12

推荐来源中的 NVD 已完成 36 页全量扫描，状态为 `ok`，不再因两页上限标记 partial。
OSV 等来源继续按详情预算记录 partial 或 stale，并保留下一次增量证据。
arXiv 和 GHSA 不在每日推荐来源中：

- arXiv 当前网络出口返回 HTTP 406；
- GHSA 未配置 `GITHUB_TOKEN`。

## 4. 产出文件

- [7 天连续运行报告](../reports/7-day-continuous-run-report.md)
- [来源健康 CSV](../reports/source-health.csv)
- [来源健康 JSON](../reports/source-health.json)
- [时延统计 JSON](../reports/latency-summary.json)
- [时延图表 SVG](../reports/latency-chart.svg)
- [来源成功率图表 SVG](../reports/source-success-chart.svg)
- [部署、调度、备份与回滚](../docs/OPERATIONS.md)
- [Docker、Compose 与 CI](../docs/DOCKER_CI_GUIDE.md)
- [运维截图目录](screenshots/)

## 5. 检查命令

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe tools\run_scheduled_collection.py --task-id manual-check
.\.venv\Scripts\python.exe tools\build_reliability_report.py --days 7 --output-dir reports
```

服务运行后：

```powershell
Invoke-RestMethod http://127.0.0.1:8010/api/health
Invoke-RestMethod http://127.0.0.1:8010/api/system/reliability
Invoke-RestMethod http://127.0.0.1:8010/api/system/alerts
```

## 6. 未提交说明

本工作副本位于：

`D:\新建文件夹\2026-09-26\ba\ai-security-intelligence-workbench`

没有修改桌面上的原项目，没有 push，也没有创建远程提交。
