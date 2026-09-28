# Docker、Compose 与 CI 使用说明

## 1. Docker 镜像

```bash
docker build -t ai-security-intelligence-workbench:local .
docker run --rm \
  --name ai-security-intel-workbench \
  -p 127.0.0.1:8000:8000 \
  -v "$PWD/data:/app/data" \
  -v "$PWD/artifacts:/app/artifacts" \
  -v "$PWD/reports:/app/reports" \
  ai-security-intelligence-workbench:local
```

镜像内包含健康检查，访问 `/api/health` 成功才视为容器健康。

## 2. Docker Compose

```bash
docker compose up --build -d
docker compose ps
docker compose logs -f workbench
```

停止：

```bash
docker compose down
```

Compose 默认仅绑定 `127.0.0.1:8000`，不直接暴露到公网。

## 3. CI

`.github/workflows/ci.yml` 包含两个任务：

1. `test`
   - 安装 Python 依赖；
   - 运行 `pytest`；
   - 运行 `node --check app/static/app.js`。
2. `container`
   - 执行 `docker build`。

## 4. 健康检查与结构化日志

```bash
curl http://127.0.0.1:8000/api/health
curl http://127.0.0.1:8000/api/system/reliability?days=7
curl http://127.0.0.1:8000/api/system/alerts
```

Docker 日志包含结构化 HTTP 请求记录和计划任务结果。告警 Webhook 可通过
`INTEL_ALERT_WEBHOOK_URL` 配置。

## 5. 文档截图

截图位于 `docs/screenshots/`：

- `01-health.png`：健康检查接口；
- `02-reliability.png`：来源可靠性 JSON；
- `03-scorecard.png`：赛题指标页面；
- `04-reports.png`：生成的报告和图表目录；
- `05-ci-workflow.png`：CI 工作流文件。

截图由 `tools/capture_operations_screenshots.py` 生成。若未安装 Playwright，
可先安装：

```bash
pip install playwright
```

脚本优先使用系统 Microsoft Edge，不需要额外下载 Chromium。

## 6. 回滚

- 镜像回滚：`docker run` 指定上一个已保存的镜像标签。
- 代码回滚：Git 切回上一个已验收提交，不上传未检查修改。
- 数据回滚：参见 `docs/OPERATIONS.md` 的数据库恢复脚本。
