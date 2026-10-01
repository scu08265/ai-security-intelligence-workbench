# 工程化交付说明

## 1. Dockerfile 与 Compose

- `Dockerfile`：Python 3.12、运行时依赖、健康检查、`APP_VERSION` 构建参数。
- `docker-compose.yml`：回环端口、数据/日志/报告卷、自动重启、健康检查。
- `scripts/deploy.ps1`：构建、启动并等待健康检查。

命令：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\deploy.ps1 -Version 0.2.2
```

## 2. CI

`.github/workflows/ci.yml` 包含：

1. Python 依赖安装；
2. `pip check`；
3. `pytest`；
4. 可靠性报告生成；
5. 前端 JavaScript 语法检查；
6. `docker compose config`；
7. Docker 镜像构建。

推送后记录指定 commit 的 CI 结果：

```powershell
.\.venv\Scripts\python.exe .\tools\record_ci_validation.py `
  --branch release/v0.2.2 `
  --head-sha <commit-sha>
```

## 3. 健康检查、结构化日志和失败告警

- 健康检查：`GET /api/health`，包含数据库、事件数、失败来源和主动跳过来源。
- Compose/Docker：内置 `/api/health` HEALTHCHECK。
- 结构化日志：JSONL 写入 `data/logs/workbench.jsonl`；`INTEL_JSON_LOGS=1` 时同时输出到容器标准输出。
- 失败告警：JSONL 写入 `data/logs/alerts.jsonl`；可额外配置 `INTEL_ALERT_WEBHOOK_URL`。
- 查询接口：`/api/system/logs`、`/api/system/alerts`。

## 4. 部署、回滚和数据库备份

部署：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\deploy.ps1 -Version 0.2.0
```

备份：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\backup_database.ps1 -KeepDays 14
```

恢复：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\restore_database.ps1 -BackupPath .\artifacts\backups\intel-YYYYMMDD-HHMMSS.sqlite
```

回滚：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\rollback_release.ps1 -Version 0.1.0
```

回滚脚本会先备份数据库，再切换到已存在的旧 Docker 镜像，并执行健康检查。

可重复的真实回滚验证：

```powershell
.\.venv\Scripts\python.exe .\tools\run_rollback_validation.py --host-port 18001
```

详细说明见 [OPERATIONS.md](OPERATIONS.md)。

## 5. 24 小时息屏采集

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install_windows_task.ps1 -IntervalHours 1 -DurationHours 24
```

任务在用户保持登录的状态下每小时运行一次，持续 24 小时；关闭显示器不会暂停任务。安装脚本会关闭自动睡眠和休眠，
并设置空闲时继续运行及唤醒后补跑。

## 6. 验收命令

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pip check
node --check app\static\app.js
docker compose config
docker build --build-arg APP_VERSION=0.2.2 -t ai-security-intelligence-workbench:0.2.2 .
```
