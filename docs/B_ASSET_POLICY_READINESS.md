# B 任务 · 策略感知资产处置建议 · 就绪度（已更新）

> **2026-09-30 更新**：策略感知处置建议已在**独立模块**中实现并通过测试，
> 未改动数据库 schema 与共享问答链路。实现细节、测试与演示见
> `docs/B_ASSET_DISPOSAL_REPORT.md`；本文件保留最初的可行性盘点结论作为背景。

## 0. 最新状态（实测）

| 项 | 状态 |
| --- | --- |
| 策略输入（六字段 + 校验 + 保守默认） | ✅ 已实现：`tools/asset_disposal_advisor.py`、`config/asset_policies.example.json` |
| 资产↔漏洞关联（版本区间/条件判定） | ✅ 复用 `app.intelligence.assess_asset`，并分为 confirmed / inferred / 缺失 |
| 可解释优先级（五分量加权） | ✅ 已实现，缺失输入记 0 分并写入 gaps，非 affected 一律输出「待核实」 |
| 运维约束检查（禁止动作/维护窗口/停机/冲突） | ✅ 已实现，独立可测；破坏性动作一律需人工批准 |
| 建议与证据输出 | ✅ 每条建议绑定 `evidence_ids`；系统只输出建议、不执行动作 |
| 测试 | ✅ `tests/test_b_asset_disposal_advisor.py` 16 passed（覆盖 12 个验收场景） |
| 演示 | ✅ `artifacts/b_eval/asset_disposal_demo.json`（3 个案例，合成资产 + 真实事件） |
| 策略进入数据库/API | ❌ 未实现（需改共享 `AssetRequest`/`storage`，需与 A 任务负责人协调） |
| 真实资产数据 | ❌ `assets` 表仍为 0 条；当前仅支持显式提供的资产文件 |

| 项 | 值 |
| --- | --- |
| 日期 | 2026-09-30 |
| 方式 | 只读盘点（未改 schema、未改 API、未改任何共享模块） |
| 结论（初次盘点） | **未就绪**：资产 0 条，四个策略字段在数据模型与 API 中都不存在 |

## 1. 现状盘点（实测）

| 项 | 实测 |
| --- | --- |
| `assets` 记录数 | **0** |
| `assessments` 记录数 | **0** |
| `AssetRequest` 现有字段 | `id, name, component, ecosystem, version, exposure, business_criticality, conditions, is_demo, authorized` |
| 优先级排序因子（`app/intelligence.py::_priority`） | `severity` / `cvss` 分数 / `business_criticality` / `exposure` |

## 2. 字段就绪度

| 需要的字段 | 在 API 模型中 | 在数据库记录中 | 状态 |
| --- | --- | --- | --- |
| 资产标识 | ✅ `id` | — | 有字段、无数据 |
| 业务重要性 | ✅ `business_criticality` | — | 有字段、无数据 |
| **维护窗口** | ❌ | ❌ | **缺失** |
| **禁止动作** | ❌ | ❌ | **缺失** |
| **负责人** | ❌ | ❌ | **缺失** |
| **可接受停机时间** | ❌ | ❌ | **缺失** |
| 关联漏洞及证据 | ⚠️ 由 `assessments` 提供 | 0 条 | 有结构、无数据 |

## 3. 结论

系统当前**只能**输出基于事件严重度与资产关键性/暴露面的**通用优先级**，
**不能**输出"考虑维护窗口、禁止动作、负责人、可停机时间"的策略感知建议。
**明确命名为"通用处置建议"，不得声称已完成个性化资产决策。**

## 4. 示例数据模板（不含任何真实敏感信息）

```json
{
  "id": "asset-example-0001",
  "name": "示例推理服务（合成）",
  "component": "vllm",
  "ecosystem": "PyPI",
  "version": "0.8.5",
  "exposure": "internal",
  "business_criticality": "medium",
  "authorized": true,
  "is_demo": true,
  "conditions": {"remote_api": true},
  "policy": {
    "maintenance_window": {"weekday": "Sun", "start": "02:00", "end": "05:00", "timezone": "Asia/Shanghai"},
    "forbidden_actions": ["restart_without_approval", "disable_auth"],
    "owner": "team-example@example.invalid",
    "acceptable_downtime_minutes": 30
  }
}
```

`policy` 是**建议的结构**，当前系统不识别它；写入前需要单独的 schema 变更授权。

## 5. 建议的输入输出契约（设计，未实施）

**输入**：事件 + 资产（含 `policy`）+ 组织策略。
**输出**：

```json
{
  "event_id": "...", "asset_id": "...",
  "recommended_actions": [
    {"action": "upgrade", "target_version": "0.24.0", "rank": 1,
     "rationale": ["命中受影响区间", "存在修复版本"], "evidence_ids": ["..."]}
  ],
  "blocked_actions": [{"action": "restart", "reason": "在禁止动作列表中"}],
  "scheduling": {"allowed_from": "...", "allowed_until": "...", "basis": "维护窗口"},
  "owner": "...",
  "limitations": ["策略字段由人工提供，系统不推断"]
}
```

**证据要求**：每条建议动作必须绑定事件/资产字段或来源 ID；无证据的动作不得输出。

## 6. 待人工核验或单独授权

1. **资产数据**：需要真实资产或明确授权使用演示资产（本轮未运行 `/api/seed`）。
2. **schema 变更**：新增 `policy` 结构需要改动共享 `AssetRequest` 与 `app/storage.py`，
   **必须先与 A 任务负责人协调**。
3. **命名**：在具备策略字段之前，界面与报告统一称"通用处置建议"。
