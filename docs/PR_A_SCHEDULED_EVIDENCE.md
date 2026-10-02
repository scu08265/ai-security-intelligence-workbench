# A 项定时运行与延迟证据

## 摘要

- 版本更新到 `0.2.3`。
- 区分 `actual_run_days`（所有采集运行）和 `scheduled_run_days`（仅 `trigger=scheduled`）。
- 可靠性 Markdown、JSON 和页面评分卡共用同一监控指标实现。
- 时延分母改用系统首次监测时间，记录监测前历史回填排除数。
- 回填 GitHub `8db19cf` 的真实 CI 结果和已通过的真实回滚证据。
- CI 增加最新 Docker 镜像版本校验和干净 Runner 上的真实回滚任务。

## 真实证据

- 计划任务运行记录：`reports/scheduler-validation.json`
- 页面/Markdown/JSON 口径一致性：`reports/monitoring-metrics-consistency.json`
- GitHub CI：`reports/ci-validation.json`
- Docker 回滚：`reports/rollback-validation.json`
- 7 天运行与时延报告：`reports/7-day-continuous-run-report.md`

## 验证命令

```powershell
.\.venv\Scripts\python.exe -m pytest -q --ignore=work
.\.venv\Scripts\python.exe tools\build_scheduler_validation.py
.\.venv\Scripts\python.exe tools\build_reliability_report.py --days 7 --output-dir reports
.\.venv\Scripts\python.exe tools\validate_monitoring_consistency.py
.\.venv\Scripts\python.exe tools\validate_evidence_consistency.py
```

## 说明

- 不补写 2026-09-29 的漏运行。
- 不把历史回填计入监测后时延分母。
- 不把人工采集伪造成计划任务运行。
- 0.2.3 的最终 Docker 和回滚结果由本分支 CI 生成并存为 artifact。
