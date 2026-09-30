# 多 Agent 运行时与自愈说明

## 1. 架构

系统新增 `app/multi_agent_runtime.py`，提供独立 Agent 实例：

- Planner
- Tool Executor
- Evidence Auditor
- Replanner
- Scheduler

每个 Agent 只拥有自己的收件箱、私有状态和已发送消息，不读取其他 Agent 的隐藏状态。Agent 之间通过显式消息总线交换：

```text
Planner -> Scheduler   plan_proposed
Scheduler -> Worker    execute_request
Worker -> Auditor      execution_result
Auditor -> Scheduler   audit_decision
Scheduler -> Replanner replan_request
Replanner -> Scheduler plan_revision
```

## 2. 审核与冲突

Auditor 会返回三种结果：

- `accepted`：工具成功且包含可核验证据。
- `rejected`：缺少证据或工具失败。
- `conflict_preserved`：不同来源存在冲突，不静默合并。

冲突保留后仍可继续处理，最终计划会单独列出 `conflict_nodes`。

## 3. 动态重规划

当节点被驳回时，Replanner 会在白名单内执行：

- 切换到已登记的备用工具。
- 在参数边界内增加一次受控重试。
- 保留冲突节点并要求证据审核。

单次任务最多允许两轮重规划。所有决策、消息和最终状态写入 `kind=multi_agent` 运行记录。

## 4. 自愈

`app/self_healing.py` 只执行预先批准的动作：

- 对 `failed` 或 `stale` 来源进行一次受控重试。
- 分类超时、限流、鉴权、格式变化和连接中断。
- 缺少 `GITHUB_TOKEN` 的 GitHub Advisory 不自动重试。
- 恢复结果写入 `kind=self_healing` 运行记录。
- 自动恢复失败后保留历史数据并转人工。

定时任务在 `partial` 或 `failed` 后，会调用自愈协调器，并将恢复结果附加到计划任务结果中。

## 5. 接口

- `POST /api/agent/multi/execute`
- `POST /api/self-healing/run`

## 6. 测试

- `tests/test_multi_agent_runtime.py`
- `tests/test_self_healing.py`
- `tests/test_scheduled_job.py`
