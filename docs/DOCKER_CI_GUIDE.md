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

## 7. 本地容器验收（两步）

验收分两步，产物都落在 `reports/`。第一步只负责把栈跑起来并留下原始日志，第二步读回真实运行状态并断言版本。

```bat
scripts\run_docker_acceptance.cmd
.\.venv\Scripts\python.exe tools\build_docker_validation.py --host-port 18000
```

| 产物 | 内容 |
| --- | --- |
| `reports/docker-acceptance.log` | `docker version`、`compose config`、完整构建输出、`compose ps` / `inspect`、`/api/health` 响应体、容器日志 |
| `reports/docker-acceptance.complete` | 等待循环结束时的容器健康状态（期望 `healthy`） |
| `reports/docker-validation.json` | 九项检查的逐项结果与 `verified` |

验收使用 `HOST_PORT=18000`，与开发用的 8000 端口分开，不会互相抢占。

第二步的九项检查与 CI 的 `container` 任务同源：Compose 配置可解析、Docker 守护进程可用、
镜像已构建、容器运行中、容器健康、健康接口可访问、`status=ok`、**容器上报版本等于 `VERSION`**。
其中最后一项是这次补上的关键约束：脚本用 `--build-arg APP_VERSION=$(VERSION)` 构建并打同名标签，
镜像内 `APP_VERSION` 环境变量因此与仓库版本一致，不再出现"仓库是 0.2.4、容器报 0.2.3"的错位。
任一项不通过时 `verified` 为 `false`，字段留空而不是补一个假定值。

第九项是凭据检查：**证据文件里不允许出现任何密钥**。这条不是形式主义——`docker compose config`
会打印解析后的完整环境，`docker inspect` 会打印容器 `Env`，两者都会把 `.env` 里的真实 token
原样抄进 `reports/docker-acceptance.log`。这个文件是入库的，一旦提交就等于把密钥写进 Git 历史
（GitHub 的 push protection 也会直接拒收推送）。因此脚本用 `--env-file` 指向一个临时空文件：
只清 shell 变量没用，Compose 的插值默认来源就是 `./.env`，变量被清掉它反而会回落到那个文件。
第二步会再扫一遍证据文件，命中密钥特征或 `.env` 里的实际值时 `verified` 直接为 `false`，
并且只报告文件与行号、不报告值本身。

只在 Windows 上需要 `scripts\run_docker_acceptance.cmd` 这层批处理：它负责从 PATH 解析 docker CLI
（本机装在 `D:\Docker`，默认安装装在 `C:\Program Files`，脚本两种都认），等待循环用 `ping` 而不是
`timeout`，因为 `timeout` 在 stdin 被重定向时（CI、计划任务、管道）会直接退出，导致健康等待形同虚设。
